package com.runtimeverification.rvmonitor.java.rvj.output.codedom.analysis;

/**
 * This interface is used to mark a class that can accept an ICodeVisitor
 * implementation.
 *
 * 
 * @see ICodeVisitor
 */
public interface ICodeVisitable {
    public void accept(ICodeVisitor visitor);
}
