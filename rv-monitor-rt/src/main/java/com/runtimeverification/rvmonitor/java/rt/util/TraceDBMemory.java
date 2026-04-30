package com.runtimeverification.rvmonitor.java.rt.util;

import java.io.*;
import java.sql.*;
import java.util.*;
import java.util.concurrent.locks.ReentrantLock;
import java.util.stream.Collectors;

import org.h2.tools.Csv;

import javax.sql.rowset.serial.SerialClob;

public class TraceDBMemory implements TraceDB {

    private static TraceDBMemory memoryDB = null;
    private HashMap<String, List<String>> monitorToTrace;
    ReentrantLock lock;
    boolean allowUpdate = true;

    public static TraceDBMemory getInstance()  {
        if (memoryDB == null)
            memoryDB = new TraceDBMemory();

        return memoryDB;
    }

    public TraceDBMemory() {
        monitorToTrace = new HashMap<>();
        lock = new ReentrantLock();
        updateSystemProperty();
    }

    @Override
    public void put(String monitorID, String trace, int length) {

    }

    /**
     * Update system properties to include dbDir information so that JUnit Listeners that work on the DB have access.
     */
    private void updateSystemProperty() {
        System.err.println("[TraceDBMemory] Set dbFilePath to: memory!");
    }

    @Override
    public void update(String monitorID, String trace, int length) {

    }

    @Override
    public void replace(String monitorID, List<String> trace) {
        lock.lock();
        if (allowUpdate)
            monitorToTrace.put(monitorID, trace);
        lock.unlock();
    }

    @Override
    public void add(String monitorID, String event) {
        lock.lock();
        if (allowUpdate)
            monitorToTrace.computeIfAbsent(monitorID, k -> new ArrayList<>()).add(event);
        lock.unlock();
    }

    @Override
    public void addRaw(String monitorID, String event) {
        add(monitorID, event);
    }

    @Override
    public void cloneMonitor(String oldMonitor, String newMonitor) {
        lock.lock();
        if (allowUpdate && monitorToTrace.containsKey(oldMonitor)) {
            // need to clone the arraylist
            monitorToTrace.put(newMonitor, new ArrayList<>(monitorToTrace.get(oldMonitor)));
        }
        lock.unlock();
    }

    @Override
    public void cloneMonitorRaw(String oldMonitor, String newMonitor) {
        cloneMonitor(oldMonitor, newMonitor);
    }

    @Override
    public void createTable() {

    }

    @Override
    public int uniqueTraces() {
        lock.lock();
        allowUpdate = false;

        int size = new HashSet<>(monitorToTrace.values()).size();
        lock.unlock();
        return size;
    }

    @Override
    public int size() {
        lock.lock();
        allowUpdate = false;

        int size = monitorToTrace.size();
        lock.unlock();
        return size;
    }

    @Override
    public List<Integer> getTraceLengths() {
        List<Integer> lengths = new ArrayList<>();
        lock.lock();
        allowUpdate = false;

        for (List<String> trace : monitorToTrace.values()) {
            lengths.add(trace.size());
        }
        lock.unlock();
        return lengths;
//        return monitorToTrace.values().stream().map(List::size).collect(Collectors.toList());
    }

    @Override
    public Map<String, Integer> getTraceFrequencies() {
        if (System.getenv("COLLECT_MONITORS") == null || !System.getenv("COLLECT_TRACES").equals("1")) {
            // Old implementation, only dump freq and traces
            Map<String, Integer> traceFrequency = new HashMap<>();
            lock.lock();
            allowUpdate = false;

            for (List<String> trace : monitorToTrace.values()) {
                String traceString = trace.toString();
                traceFrequency.put(traceString, traceFrequency.getOrDefault(traceString, 0) + 1);
            }
            lock.unlock();
            return traceFrequency;
        }

        // New implementation, dump traceID, and monitor freq
        Map<String, Integer> traceToID = new HashMap<>(); // Map actual trace to trace ID
        Map<Integer, Map<String, Integer>> specFrequency = new HashMap<>(); // Map trace ID to <Spec, Freq>

        lock.lock();
        allowUpdate = false;

        int nextTraceID = 0;
        int traceID;
        for (Map.Entry<String, List<String>> entry : monitorToTrace.entrySet()) {
            String traceString = entry.getValue().toString();
            if (traceToID.containsKey(traceString)) {
                traceID = traceToID.get(traceString);
            } else {
                traceID = nextTraceID++;
                traceToID.put(traceString, traceID);
            }

            Map<String, Integer> f = specFrequency.computeIfAbsent(traceID, k -> new HashMap<>());
            String specName = entry.getKey().split("#")[0];
            f.put(specName, f.getOrDefault(specName, 0) + 1);
        }
        lock.unlock();

        writeTraceAndSpecFrequencyToFile(specFrequency);
        return traceToID;
    }

    private void writeTraceAndSpecFrequencyToFile(Map<Integer, Map<String, Integer>> specFrequency) {
        if (System.getenv("TRACEDB_PATH") == null) {
            return;
        }

        String csvDir = System.getenv("TRACEDB_PATH") + TraceDatabase.getInstance().randomFileName + File.separator + "specs-frequency.csv";
        try {
            FileWriter fileWriter = new FileWriter(csvDir);
            PrintWriter writer = new PrintWriter(fileWriter);
            int i = 0;
            for (Map.Entry<Integer, Map<String, Integer>> entry : specFrequency.entrySet()) {
                writer.println(entry.getKey() + " " + entry.getValue().toString());
                i++;
                if (i % 10 == 0) {
                    writer.flush();
                }
            }

            writer.println("OK");
            writer.flush();
            writer.close();
        } catch (Exception ex) {
            printError(Arrays.toString(ex.getStackTrace()));
        }
    }

    @Override
    public void dump() {
        if (System.getenv("TRACEDB_PATH") == null) {
            return;
        }

        lock.lock();

        String csvDir = System.getenv("TRACEDB_PATH") + TraceDatabase.getInstance().randomFileName + File.separator + "monitor-table.csv";
        try {
            FileWriter fileWriter = new FileWriter(csvDir);
            PrintWriter writer = new PrintWriter(fileWriter);
            writer.println("");
            int i = 0;
            for (Map.Entry<String ,List<String>> entry : monitorToTrace.entrySet()) {
                writer.println(entry.getKey() + " " + entry.getValue());
                i++;
                if (i % 10 == 0) {
                    writer.flush();
                }
            }
            writer.flush();
            writer.close();
        } catch (IOException ignored) {}

        lock.unlock();
    }

    private void printError(String message) {
        try {
            FileWriter fileWriter = new FileWriter(System.getenv("TRACEDB_PATH") + TraceDatabase.getInstance().randomFileName + File.separator +
                    "error-spec.txt");
            PrintWriter writer = new PrintWriter(fileWriter);
            writer.println(message);
            writer.flush();
            writer.close();
        } catch (Exception ignored) {}
    }
}
