package com.runtimeverification.rvmonitor.java.rt.util;

import java.util.List;
import java.util.Map;

public interface TraceDB {

    void put(String monitorID, String trace, int length);

    void update(String monitorID, String trace, int length);

    default void replace(String monitorID, List<String> trace) {}

    default void add(String monitorID, String event) {}
    default void addRaw(String monitorID, String event) {}

    default void cloneMonitor(String oldMonitor, String newMonitor) {}
    default void cloneMonitorRaw(String oldMonitor, String newMonitor) {}

    default void setCurrentTest(String test) {}

    void createTable();

    int uniqueTraces();

    int size();

    List<Integer> getTraceLengths();

    Map<String, Integer> getTraceFrequencies();

    void dump();

}
