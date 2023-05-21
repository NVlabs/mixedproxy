module ptx

///////////////////////////////////////////////////////////////////////////////
// Addresses
///////////////////////////////////////////////////////////////////////////////

/* An Address is an abstract representation of a single memory address.  From
 * an implementation PoV: virtual addresses, not physical addresses. */
sig Address {
  alias: set Address,
}

fun aliases : Address->Address { Address <: *(alias + ~alias) }


///////////////////////////////////////////////////////////////////////////////
// Scopes and Threads
///////////////////////////////////////////////////////////////////////////////

abstract sig Scope {}
one sig System extends Scope { devices: set Device }
sig Device extends Scope { blocks: set Block }
sig Block extends Scope { threads: set Thread }
sig Thread extends Scope { start: one Op }

fun subscope : Scope->Scope { devices + blocks + threads }


///////////////////////////////////////////////////////////////////////////////
// Proxies
///////////////////////////////////////////////////////////////////////////////

abstract sig Proxy {}
one sig GenericProxy extends Proxy {}
one sig SurfaceProxy extends Proxy {}
one sig TextureProxy extends Proxy {}
one sig ConstantProxy extends Proxy {}

fun GenericOps : set Op { GenericProxy.~proxy }


////////////////////////////////////////////////////////////////////////////////
// Ops
////////////////////////////////////////////////////////////////////////////////

abstract sig Op {
  po: lone Op
}

abstract sig ScopedOp extends Op {
  scope: one Scope
}


abstract sig MemoryOp extends ScopedOp {
  address: one Address,
  proxy: one Proxy,
  value: one Int,

  /* see the note about observation below */
  // observation: set MemoryOp,
}


sig Read extends MemoryOp {
  rmw: lone Write,
  dep: set Op
}
sig ReadAcquire extends Read { } { scope not in Thread }

sig Write extends MemoryOp {
  rf: set Read,
  co: set Write,
}
sig WriteRelease extends Write { } { scope not in Thread }

abstract sig Fence extends ScopedOp {} { scope not in Thread }
sig FenceAcqRel extends Fence { }
sig FenceSC extends Fence {
  sc: set FenceSC,
}

sig ProxyFence extends Op {
  proxy_fence_proxy: set Proxy,
}

sig AliasFence extends Op {}


////////////////////////////////////////////////////////////////////////////////
// Basic Derived Relations
////////////////////////////////////////////////////////////////////////////////

/* program order, same (virtual) address */
fun po_loc : Op->Op { same_alias[^po] }

/* from-reads */
fun fr : Read->Write {
  ~rf.^co
  +
  /* also include reads that read from the initial state */
  same_location[(Read - (Write.rf))->Write]
}

/* communication */
fun com : MemoryOp->MemoryOp { rf + ^co + fr }

fun ReleaseFences : Fence { FenceAcqRel + FenceSC }
fun AcquireFences : Fence { FenceAcqRel + FenceSC }


///////////////////////////////////////////////////////////////////////////////
// Model Axioms
////////////////////////////////////////////////////////////////////////////////

pred causality {
  irreflexive[optional[com].cause]
}
pred atomicity {
  no strong[fr].(strong[co]) & rmw
}
pred coherence {
  same_location[Write <: cause :> Write] in ^co
}
pred seq_cst {
  FenceSC <: cause :> FenceSC in sc
}
pred no_thin_air {
  acyclic[rf + dep]
}

pred sc_per_location {
  acyclic[strong[com] + po_loc]
}

pred ptx_mm {
  no_thin_air and atomicity and coherence and causality and seq_cst and sc_per_location
}


///////////////////////////////////////////////////////////////////////////////
// Causality Components
////////////////////////////////////////////////////////////////////////////////

fun cause : Op->Op {
  optional[observation].proxy_preserved_cause_base
}

fun sync : Op->Op {
  release_sequence.^observation.acquire_sequence
}

fun release_sequence : Op->Op {
  (WriteRelease <: optional[po_loc] :> Write)
  + (ReleaseFences <: ^po :> Write)
}

/* There are two definitions: the original version was the raw definition
 * listed first, but PTX uses a free relation defined recursively, as shown
 * second.  The two should be equivalent. */
fun observation : Op->Op {
  strong[rf] + rmw
}
// fact { observation in ^(strong[rf] + rmw) }
// fact { strong[rf] in observation }
// fact { observation.rmw.observation in observation }

fun acquire_sequence : Op->Op {
  (Read <: optional[po_loc] :> ReadAcquire)
  /* 2) A Read followed by an AcquireFence (or greater) */
}

////////////////////////////////////////////////////////////////////////////////
// Proxy-aware causality ordering
////////////////////////////////////////////////////////////////////////////////

/* The set of Ops on which a ProxyFence has an effect */
fun proxy_fence_ops : ProxyFence->Op {
  /* Ops in the same Proxy as the ProxyFence */
  proxy_fence_proxy.~proxy
  
  /* ...and in the same thread Block */
  & same_block_r
}

fun same_block_r : Op->Op {
  *~po.~start.~threads.threads.start.*po
}

fun same_proxy_r : Op->Op {
  proxy.~proxy
}

fun cause_base : Op->Op {
  ^po + *po.^((sc + sync).*po)
}

fun proxy_preserved_cause_base : Op->Op {
  /* No proxy fences or alias fences */
  same_alias[GenericOps <: cause_base :> GenericOps]
  + same_alias[cause_base & same_block_r & same_proxy_r]

  /* Proxy fence for src */
  + same_alias[(cause_base & ~proxy_fence_ops).cause_base :> GenericOps]

  /* Proxy fence for dst */
  + same_alias[GenericOps <: cause_base.(cause_base & proxy_fence_ops)]

  /* Proxy fence for src and dst */
  + same_alias[(cause_base & ~proxy_fence_ops).cause_base.(cause_base & proxy_fence_ops)]

  /* Alias fence */
  + same_location[GenericOps <: cause_base.(AliasFence <: cause_base ) :> GenericOps]

  /* Proxy fence for src plus alias fence */
  + same_location[(cause_base & ~proxy_fence_ops).(cause_base :> AliasFence).cause_base :> GenericOps]

  /* Proxy fence for dst plus alias fence */
  + same_location[GenericOps <: cause_base.(AliasFence <: cause_base).(cause_base & proxy_fence_ops)]

  /* Proxy fence for src and dst plus alias fence */
  + same_location[(cause_base & ~proxy_fence_ops).(cause_base :> AliasFence).cause_base.(cause_base & proxy_fence_ops)]
}


////////////////////////////////////////////////////////////////////////////////
// Basic model constraints
////////////////////////////////////////////////////////////////////////////////

//address
fact com_addr { com in same_location_r }
fun same_location_r : Op->Op { address.aliases.~address }
fun same_location[rel: Op->Op] : Op->Op { rel & same_location_r }
fun same_alias_r : Op->Op { address.~address }
fun same_alias[rel: Op->Op] : Op->Op { rel & same_alias_r }

//po
fact { acyclic[po] }
fact { all o: Op | one t: Thread | t->o in start.*po }

//dep
fact { dep in ^po }

//rmws
fact { rmw in same_alias[po & dep & scope.~scope] }

//scope
fact { subscope.~subscope in iden }
fact { all s: Scope | System in s.*~subscope }
fact { acyclic[subscope] }
fact { scope in scopes }

//rf
fact { rf.~rf in iden }
fact { all r: Read |
  some r.~rf => r.value = r.~rf.value else r.value = 0
}

//co
fact {
  all a: Address | all s: Scope | all p: Proxy |
    total[co, scoped[s] & inside[s] & p.~proxy & (a.~address & Write)]
}

//sc
fact {
  all s: Scope | total[sc, scoped[s] & inside[s] & FenceSC]
}


///////////////////////////////////////////////////////////////////////////////
// =Helper functions=

fun symmetric[r: univ->univ] : univ->univ { r & ~r }

fun optional[f: univ->univ] : univ->univ { iden + f }

pred irreflexive[rel: univ->univ] { no iden & rel }

pred acyclic[rel: univ->univ] { irreflexive[^rel] }

pred total[rel: univ->univ, bag: univ] {
  all disj e, e2: bag | e->e2 + e2->e in ^rel + ^~rel
  acyclic[rel]
}

fun scopes : set Op->Scope {
  *~po.~start.*~subscope
}
fun inside[s: Scope] : Op {
  s.~scopes
}
fun scoped[s: Scope] : Op {
  s.*~subscope.~scope
}
fun strong_r : Op->Op {
  symmetric[scope.~scopes] & proxy.~proxy
}
fun strong[r: Op->Op]: Op->Op {
  r & strong_r
}

////////////////////////////////////////////////////////////////////////////////
