#!/usr/bin/env python3

import sys
import output


def _s(arg, prefix="."):
    "print each argument prefixed by `prefix`"
    if arg is None:
        return ""
    elif isinstance(arg, list):
        return "".join([prefix + a for a in arg])
    else:
        return prefix + str(arg)


class AlloyEmitter:
    def __init__(self, model):
        self.text = model + "\n"
        self.threads = set()
        self.blocks = set()
        self.devices = set()
        self.po_expr = {}
        self._reg_values = set()

    def _write(self, txt):
        output.verbose("Alloy: " + txt.rstrip())
        self.text += txt

    def _arithmetic_op(self, op):
        try:
            return {"add": "fun/add"}[op]
        except KeyError:
            raise Exception(f"no Alloy mapping for atomic operation {op}")

    def _scope(self, scope):
        try:
            return {
                None: "Thread",
                "cta": "Block",
                "gpu": "Device",
                "sys": "System",
            }[scope]
        except KeyError:
            raise Exception(f"no Alloy mapping for scope {scope}")

    def _proxy(self, proxy):
        try:
            return {
                None: "GenericProxy",
                "generic": "GenericProxy",
                "surface": "SurfaceProxy",
                "texture": "TextureProxy",
                "constant": "ConstantProxy",
            }[proxy]
        except KeyError:
            raise Exception(f"no Alloy mapping for proxy {proxy}")

    def integer(self, value):
        return str(value)

    def value(self, name):
        return f"{name}.value"

    def arithmetic(self, op, values):
        return f" {self._arithmetic_op(op)} ".join(values)

    def union(self, values):
        return f" + ".join(values)

    def address(self, name, alias):
        self._write(
            f"one sig {name} extends Address {{}}\n"
        )
        if alias:
            self._write(f"fact {{ {name}.alias = {alias} }}\n")
        else:
            self._write(f"fact {{ no {name}.alias }}\n")

    def virtual_synonym(self, name, alias):
        self._write(f"fun {name} : Address {{ {alias} }}\n")

    def thread(self, d, b, t, line=None):
        self._write(f"\n// Thread {t}\n")
        output.godbolt(f"\n// Thread {t}", line)
        self.current_thread = t

        if t in self.po_expr:
            self._write("// (continued...)\n")
        else:
            if d and d not in self.devices:
                self.devices.add(d)
                self._write(f"one sig {d} extends Device {{}}\n")

            if b and b not in self.blocks:
                self.blocks.add(b)
                self._write(
                    f"one sig {b} extends Block {{}} {{ this in {d}.blocks }}\n"
                )

            if t in self.threads:
                raise Exception("Thread {t} multiply defined")
            self._write(
                f"one sig {t} extends Thread {{}} {{ this in {b}.threads }}\n"
            )

            self.po_expr[t] = f"{t}.start"

    def instruction(self, name, op):
        self._write(f"\n")
        self._write(f"one sig {name} extends {op} {{}}\n")
        self._write(
            f"fact {{ {name} = {self.po_expr[self.current_thread]} }}\n"
        )
        self.po_expr[self.current_thread] = f"{name}.po"

    def set_register(self, reg, value, return_value):
        if reg:
            self._write(f"one sig {reg} {{\n")
            self._write(f"  value: one Int,\n")
            self._write("} {\n")
            self._write(f"  value = {value}\n")
            self._write("}\n")

        if return_value is not None:
            self._write(f"pred {reg}_value {{ {value} = {return_value} }}\n")
            self._reg_values.add(f"{reg}_value")
        else:
            self._write("// no specified return value\n")

    def scoped_op(self, name, op, scope):
        self.instruction(name, op)
        self._write(f"fact {{ {name}.scope in {self._scope(scope)} }}\n")

    def memory_op(self, name, op, scope, proxy, address):
        self.scoped_op(name, op, scope)
        self._write(f"fact {{ {name}.proxy = {self._proxy(proxy)} }}\n")
        self._write(f"fact {{ {name}.address = {address} }}\n")

    def load(self, name, sem, scope, proxy, dst, address, return_value, line):
        asm = f"ld{_s(sem)}{_s(scope)}{_s(proxy, '.proxy_')} {dst}, {address} {_s(return_value, '== ')}"
        self._write(f"// operation {name}: {asm}")
        output.godbolt(asm, line)
        op = {
            None: "Read",
            "weak": "Read",
            "relaxed": "Read",
            "acquire": "ReadAcquire",
        }[sem]
        self.memory_op(name, op, scope, proxy, address)
        self.set_register(dst, self.value(name), return_value)

    def store(self, name, sem, scope, proxy, dst, value, is_rmw, line):
        asm = f"st{_s(sem)}{_s(scope)}{_s(proxy, '.proxy_')} {dst}, {value}"
        self._write(f"// operation {name}: {asm}")
        output.godbolt(asm, line)
        op = {
            None: "Write",
            "weak": "Write",
            "relaxed": "Write",
            "release": "WriteRelease",
        }[sem]
        self.memory_op(name, op, scope, proxy, dst)
        self._write(f"fact {{ {name}.value = {value} }}\n")
        if is_rmw:
            self._write(f"fact {{ some {name}.~rmw }}\n")
        else:
            self._write(f"fact {{ no {name}.~rmw }}\n")

    def atom(
        self,
        name,
        atomic_op,
        sem,
        scope,
        proxy,
        dst,
        address,
        value,
        return_value,
        line,
    ):
        op1, op2 = {
            "relaxed": ("relaxed", "relaxed"),
            "acquire": ("acquire", "relaxed"),
            "release": ("relaxed", "release"),
            "acq_rel": ("acquire", "release"),
        }[sem]
        self.load(
            name + "_r", op1, scope, proxy, dst, address, return_value, line
        )
        store_value = self.arithmetic(
            atomic_op, [self.value(name + "_r"), value]
        )
        self.store(
            name + "_w", op2, scope, proxy, address, store_value, True, line
        )

    def fence(self, name, sem, scope, line):
        asm = f"fence{_s(sem)}{_s(scope)}"
        self._write(f"// operation {name}: {asm}")
        output.godbolt(asm, line)
        op = {
            "acq_rel": "FenceAcqRel",
            "sc": "FenceSC",
        }[sem]
        self.scoped_op(name, op, scope)

    def proxy_fence(self, name, proxy, line):
        asm = f"fence{_s(proxy, '.proxy_')}"
        self._write(f"// operation {name}: {asm}")
        output.godbolt(asm, line)
        self.instruction(name, "ProxyFence")
        self._write(f"fact {{ {name}.proxy_fence_proxy = {self._proxy(proxy)} }}\n")

    def alias_fence(self, name, line):
        asm = f"fence.proxy.alias"
        self._write(f"// operation {name}: {asm}")
        output.godbolt(asm, line)
        self.instruction(name, "AliasFence")

    def command_and(self, a, b):
        return f"({a} and {b})"

    def command_or(self, a, b):
        return f"({a} or {b})"

    def command_not(self, ab):
        return f"(not {a})"

    def command_not(self, a):
        return f"not {a}"

    def command_equal(self, a, b):
        return f"({a} = {b})"

    def command(self, name, pred, sanity, expected, line):

        prefixes = ["ptx_mm"]
        for i in self._reg_values:
            prefixes.append(i)

        if expected:
            command = "run"
            if not sanity:
                pred = f"{' and '.join(prefixes)} and ({pred})"
        else:
            command = "check"
            if not sanity:
                pred = f"{' => '.join(prefixes)} => ({pred})"

        asm = f"{command} {name} {{ {pred} }} for 1 but 6 Int"
        self._write(f"{asm}\n\n")
        output.godbolt(f"\n{asm}", line)
