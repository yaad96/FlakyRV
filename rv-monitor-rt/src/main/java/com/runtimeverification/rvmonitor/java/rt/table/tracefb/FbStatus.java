package com.runtimeverification.rvmonitor.java.rt.table.tracefb;

import java.util.*;
    
public class FbStatus {
    private int uniqScore = 0;
    
    private double gracePeriod = 0.0;
    private int dupLength = 0;
    private int periodLength = 0;	
    private int uniqOccur = 0;

    private boolean lastActivated = true;

    public boolean ifUniqTrace() {
	if (uniqScore >= 10) {
	    return true;
        }
	return false;
    }

    public boolean processDup() {
	uniqScore -= 1;

	if (++dupLength <= gracePeriod) {
	    lastActivated = true;
	} else {
	    lastActivated = false;
	}
    	return lastActivated;
    }

    public boolean processUniq() {
	uniqScore += 2;
	
	if (dupLength > 0) {
	    periodLength += ++dupLength;
	    uniqOccur++;
	    
	    gracePeriod = (double)periodLength/uniqOccur;
	}
	dupLength = 0;

	boolean retValue = lastActivated;
	lastActivated = true;

	return retValue;
    }
}
