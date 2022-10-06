/* Alloy Analyzer 4 -- Copyright (c) 2006-2009, Felix Chang
 *
 * Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files
 * (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify,
 * merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is
 * furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES
 * OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE
 * LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF
 * OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
 */

/* RunAlloy.java
 * 
 * This is a wrapper that we repurposed from some example Alloy API code.
 *
 * This program takes in an Alloy model (-f alloymodelname.als), and the name
 * of a run statement (or multiple run statements) to generate instances
 * using. This will continue generating instances until there are none
 * remaining. This program prints each instance to stdout for the Alloy parser
 * to parse, filter, and turn into a litmus test.
 */

import java.util.*;
import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.io.PrintWriter;
import java.io.FileNotFoundException;
import java.io.File;
import java.io.IOException;
import edu.mit.csail.sdg.alloy4.A4Reporter;
import edu.mit.csail.sdg.alloy4.Err;
import edu.mit.csail.sdg.alloy4.ErrorWarning;
import edu.mit.csail.sdg.ast.Command;
import edu.mit.csail.sdg.ast.CommandScope;
import edu.mit.csail.sdg.ast.Expr;
import edu.mit.csail.sdg.ast.ExprList;
import edu.mit.csail.sdg.ast.Module;
import edu.mit.csail.sdg.parser.CompUtil;
import edu.mit.csail.sdg.translator.A4Options;
import edu.mit.csail.sdg.translator.A4Solution;
import edu.mit.csail.sdg.translator.TranslateAlloyToKodkod;

/** This class demonstrates how to access Alloy4 via the compiler methods. */

public final class RunAlloy {
    public static void main(String[] args) throws Err, FileNotFoundException, IOException {
        boolean verbose = false;
        String filename = "";

        if (args.length > 1 && args[0].equals("-i")) {
            filename = args[1];
        }

        A4Reporter rep = new A4Reporter() {
            // For example, here we choose to display each "warning" by printing it to System.out
            @Override public void warning(ErrorWarning msg) {
                System.err.print("Relevance Warning:\n"+(msg.toString().trim())+"\n\n");
                System.err.flush();
            }
        };

        String input = "";
        if (filename.length() == 0) {
            Scanner scanner = new Scanner(System.in);
            while (scanner.hasNextLine()){
                input += scanner.nextLine() + "\n";
            }
        } else {
            input = new Scanner(new File(filename)).useDelimiter("\\Z").next();
        }

        if (verbose) {
            System.out.println(input);
        }
        
        // Parse+typecheck the model
        //Module world = CompUtil.parseEverything_fromFile(rep, null, filename);
        Module world = CompUtil.parseEverything_fromString(rep, input);

        // Choose some default options for how you want to execute the commands
        A4Options options = new A4Options();

        // This requires 32-bit java in windows
        //options.solver = A4Options.SatSolver.MiniSatJNI;

        // If there are specified commands, run them
        int exit_code = 0;
        for (Command command: world.getAllCommands()) {
            if (verbose) {
                System.out.println("Executing: " + command.label);
            }
            // Execute the command
            A4Solution ans = TranslateAlloyToKodkod.execute_command(rep, world.getAllReachableSigs(), command, options);

            // Print the outcome
            if (!command.check && command.label.length() >= 6 &&
                    command.label.substring(0,6).equals("check_")) {
                if(ans.satisfiable()) {
                    System.out.println(command.label + ": SAT, outcome permitted");
                } else {
                    System.out.println(command.label + ": UNSAT, outcome not permitted");
                }
            } else if (!command.check && command.label.length() >= 6 &&
                    command.label.substring(0,6).equals("sanity")) {
                if(ans.satisfiable()) {
                    if (verbose) {
                        System.out.println(command.label + ": SAT, outcome permitted");
                    }
                } else {
                    System.out.println(command.label + ": UNSAT, outcome not permitted, breaks expectation");
                    System.out.println("\t!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!");
                    exit_code = 10;
                }
            } else if (command.check) {
                if(ans.satisfiable()) {
                    System.out.println(command.label + ": SAT, assertion violated, breaks expectation");
                    System.out.println("\t!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!");
                    exit_code = 10;
                    Expr value = world.parseOneExpressionFromString("MemoryOp <: value");
                    System.out.println("\tvalue=" + ans.eval(value).toString());
                } else {
                    System.out.println(command.label + ": UNSAT, assertion confirmed, matches expectation");
                }
            } else {
                if(ans.satisfiable()) {
                    System.out.println(command.label + ": SAT, outcome permitted, matches expectation");
                } else {
                    System.out.println(command.label + ": UNSAT, outcome not permitted, breaks expectation");
                    System.out.println("\t!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!");
                    exit_code = 10;
                }
            }
        }

        System.exit(exit_code);
    }
}
