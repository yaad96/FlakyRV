// Copyright (c) 2002-2014 JavaMOP Team. All Rights Reserved.
/*
 * Copyright (C) 2008 Feng Chen.
 * 
 * This file is part of JavaMOP parser.
 *
 * JavaMOP is free software: you can redistribute it and/or modify
 * it under the terms of the GNU Lesser General Public License as published by
 * the Free Software Foundation, either version 3 of the License, or
 * (at your option) any later version.
 *
 * JavaMOP is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU Lesser General Public License for more details.
 *
 * You should have received a copy of the GNU Lesser General Public License
 * along with JavaMOP.  If not, see <http://www.gnu.org/licenses/>.
 */

package javamop.parser.astex.visitor;

import java.util.Iterator;

import com.github.javaparser.ast.NodeList;
import com.github.javaparser.ast.ImportDeclaration;
import com.github.javaparser.ast.stmt.BlockStmt;
import com.github.javaparser.ast.body.BodyDeclaration;
import com.github.javaparser.printer.MOPPrinter;
import com.github.javaparser.printer.configuration.PrinterConfiguration;
import javamop.parser.ast.mopspec.MOPParameter;
import javamop.parser.ast.mopspec.MOPParameters;
import javamop.parser.ast.mopspec.SpecModifierSet;
import javamop.parser.astex.MOPSpecFileExt;
import javamop.parser.astex.aspectj.EventPointCut;
import javamop.parser.astex.aspectj.HandlerPointCut;
import javamop.parser.astex.mopspec.EventDefinitionExt;
import javamop.parser.astex.mopspec.ExtendedSpec;
import javamop.parser.astex.mopspec.FormulaExt;
import javamop.parser.astex.mopspec.HandlerExt;
import javamop.parser.astex.mopspec.JavaMOPSpecExt;
import javamop.parser.astex.mopspec.PropertyAndHandlersExt;
import javamop.parser.astex.mopspec.ReferenceSpec;

/**
 * @author Julio Vilmar Gesser
 */

public class DumpVisitor extends javamop.parser.ast.visitor.DumpVisitor implements MOPVoidVisitor<Void> {

	public DumpVisitor(PrinterConfiguration configuration) {
		super(configuration, new MOPPrinter());
	}

	// - JavaMOP components

	// All extended componenets

	public void visit(MOPSpecFileExt f, Void arg) {
		printer.println("(PackageDeclaration)");
		if (f.getPakage() != null)
			f.getPakage().accept(this, arg);
		printer.println("(ImportDeclaration)");
		if (f.getImports() != null) {
			for (ImportDeclaration i : f.getImports()) {
				i.accept(this, arg);
			}
			printer.println();
		}
		printer.println("(Specification)");
		if (f.getSpecs() != null) {
			for (JavaMOPSpecExt i : f.getSpecs()) {
				i.accept(this, arg);
				printer.println();
			}
		}
	}

	// soha: printing out references to other spec
	public void visit(ReferenceSpec r, Void arg) {
		printer.print("ReferenceSpec: ");
		if (r.getSpecName() != null)
			if (r.getReferenceElement() != null)
				printer.print(r.getSpecName() + "." + r.getReferenceElement());
			else
				printer.print(r.getSpecName());
		else if (r.getReferenceElement() != null)
			printer.print(r.getReferenceElement());
		printer.println("");
	}

	public void visit(JavaMOPSpecExt s, Void arg) {
		printer.print("Public: ");
		if (s.isPublic())
			printer.print("public ");
		printer.println("");
		printer.print("Modifiers: ");
		printSpecModifiers(s.getModifiers());
		printer.println("");
		printer.println("Name: " + s.getName());
		printer.print("Parameters: ");
		printSpecParameters(s.getParameters(), arg);
		printer.println("");
		printer.print("InMethod: ");
		if (s.getInMethod() != null) {
			printer.print(" within ");
			printer.print(s.getInMethod());
			// s.getInMethod().accept(this, arg);
		}
		printer.println("");
		printer.print("ExtendedSpecs: ");
		if (s.hasExtend()) {
			printer.print(" includes ");
			int size = 1;
			for (ExtendedSpec e : s.getExtendedSpec()) {
				e.accept(this, arg);
				if (size != s.getExtendedSpec().size())
					printer.print(",");
				size++;
			}
		}
		printer.println("");

		// printer.println(" {");
		// printer.indent();

		printer.print("Declarations: ");
		if (s.getDeclarations() != null) {
			printMembers(s.getDeclarations(), (Void)arg);
		}
		printer.println("");

		printer.println("(Events) ");
		if (s.getEvents() != null) {
			for (EventDefinitionExt e : s.getEvents()) {
				e.accept(this, arg);
			}
		}
		// printer.println("");

		printer.println("(Properties) ");
		if (s.getPropertiesAndHandlers() != null) {
			for (PropertyAndHandlersExt p : s.getPropertiesAndHandlers()) {
				p.accept(this, arg);
			}
		}
		printer.println("");

		// printer.unindent();
		// printer.println("}");
	}

	public void visit(EventDefinitionExt e, Void arg) {
		printer.print("Abstract: ");
		if (e.isAbstract())
			printer.print("abstract "); // Soha:printing out abstract keyword

		printer.println("");
		printer.println("Name: " + e.getId());
	        printer.println("Position: " + e.getPos());
		printSpecParameters(e.getParameters(), arg);
		printer.print("Returning: ");
		if (e.hasReturning()) {
			printer.print("returning");
			if (e.getRetVal() != null)
				printSpecParameters(e.getRetVal(), arg);
			printer.print(" ");
		}
		printer.println("");
		printer.print("Throwing: ");
		if (e.hasThrowing()) {
			printer.print("throwing");
			if (e.getThrowVal() != null)
				printSpecParameters(e.getThrowVal(), arg);
			printer.print(" ");
		}
		printer.println("");
		if (!e.isAbstract()) {
			// printer.print(":");

			// e.getPointCut().accept(this, arg);
			printer.print("PointCut: ");
			printer.print(e.getPointCutString());
			printer.println("");
			printer.print("Block: ");
			if (e.getAction() != null) {
				e.getAction().accept(this, arg);
			}
		} else
			printer.print(";");

		printer.println();
	}

	public void visit(PropertyAndHandlersExt p, Void arg) {
		if (p.getProperty() != null)
			p.getProperty().accept(this, arg);
		printer.println("(Handlers) ");
		for (String event : p.getHandlers().keySet()) {
			printer.println("Event: " + event);
			for (HandlerExt h : p.getHandlerList()) { // i need to remove that
														// later, i'm using it
														// now to just make sure
														// that things are
														// parsed correctly.
														// Soha.
				if (h.getState() == event) { // Soha: printing out the new
												// syntax of the handler and
												// property
					if ((h.getReferenceSpec().getSpecName() != null) || (h.getReferenceSpec().getReferenceElement() != null))
						printer.print("@");
					h.accept(this, arg);
				}
			}
			printer.print("Block: ");
			BlockStmt stmt = p.getHandlers().get(event);
			printer.println("@" + event);
			printer.indent();
			stmt.accept(this, arg);
			printer.unindent();
			printer.println();
		}
	}
	
	public void visit(FormulaExt f, Void arg) {
		printer.print("Formula: ");
		printer.println(f.getType()+ " "+ f.getName() + ": " + f.getFormula().trim());
	}

	public void visit(HandlerExt h, Void arg) {
		printer.println("State: " + h.getState());
		h.getReferenceSpec().accept(this, arg);
	}

	public void visit(ExtendedSpec extendedSpec, Void arg) {
		printer.print("ExtendedSpec: ");
		printer.print(" " + extendedSpec.getName());
		if (extendedSpec.isParametric()) {
			printer.print("(");
			int size = 1;
			for (String extendedParameters : extendedSpec.getParameters()) {
				printer.print(extendedParameters);
				if (size != extendedSpec.getParameters().size())
					printer.print(",");
				size++;
			}

			printer.print(")");
		}
	}

	// - AspectJ components --------------------

	public void visit(EventPointCut p, Void arg) {
		printer.print("event" + "(");
		p.getReferenceSpec().accept(this, arg);
		printer.print(")");
	}

	public void visit(HandlerPointCut p, Void arg) {
		printer.print("handler" + "(");
		p.getReferenceSpec().accept(this, arg);
		printer.print("@" + p.getState());
		printer.print(")");
	}

	protected void printSpecModifiers(int modifiers) {
		if (SpecModifierSet.isAvoid(modifiers)) {
			printer.print("avoid ");
		}
		if (SpecModifierSet.isConnected(modifiers)) {
			printer.print("connected ");
		}
		if (SpecModifierSet.isDecentralized(modifiers)) {
			printer.print("decentralized ");
		}
		if (SpecModifierSet.isEnforce(modifiers)) {
			printer.print("enforce ");
		}
		if (SpecModifierSet.isFullBinding(modifiers)) {
			printer.print("full-binding ");
		}
		if (SpecModifierSet.isPerThread(modifiers)) {
			printer.print("perthread ");
		}
		if (SpecModifierSet.isSuffix(modifiers)) {
			printer.print("suffix ");
		}
		if (SpecModifierSet.isUnSync(modifiers)) {
			printer.print("unsynchronized ");
		}
	}
	protected void printSpecParameters(MOPParameters args, Void arg) {
		printer.print("(");
		if (args != null) {
			for (Iterator<MOPParameter> i = args.iterator(); i.hasNext();) {
				MOPParameter t = i.next();
				t.accept(this, arg);
				if (i.hasNext()) {
					printer.print(", ");
				}
			}
		}
		printer.print(")");
	}
}
