package com.runtimeverification.rvmonitor.java.rt.observable;

import java.io.File;
import java.io.FileNotFoundException;
import java.io.FileWriter;
import java.io.PrintWriter;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.Map;

import com.runtimeverification.rvmonitor.java.rt.util.TraceDatabase;
import com.runtimeverification.rvmonitor.java.rt.util.TraceUtil;

public class AllMonitorTraceCollector extends MonitorTraceCollector {

    private boolean doAnalysis;
    private boolean writeLocationMap;

    private PrintWriter locationMapWriter;

    public boolean isDoAnalysis() {
        return doAnalysis;
    }

    public AllMonitorTraceCollector(PrintWriter writer, boolean doAnalysis, boolean writeLocationMap,
                                    File locationMapFile, String dbPath, String dbConfigFile) {
        super(writer, dbPath, dbConfigFile);
        this.doAnalysis = doAnalysis;
        this.writeLocationMap = writeLocationMap;
        TraceUtil.updateLocationMapFromFile(locationMapFile);
        try {
            this.locationMapWriter = new PrintWriter(locationMapFile);
        } catch (FileNotFoundException ex) {
            printError(ex.getMessage());
        }
    }

    @Override
    public void onCompleted() {
        if (doAnalysis) {
            processTracesWithAnalysis();
        } else {
            processTracesWithoutAnalysis();
        }
        writer.flush();
        writer.close();
        if (writeLocationMap) {
            writeLocationMapToFile();
        }
    }

    private void writeLocationMapToFile() {
        try {
            locationMapWriter.println("=== LOCATION MAP ===");
            List<Map.Entry<String, Integer>> locations = new ArrayList<>(TraceUtil.getLocationMap().entrySet());
            locations.sort(Map.Entry.comparingByValue());
            for (Map.Entry<String, Integer> location : locations) {
                locationMapWriter.println(location.getValue() + " " + location.getKey());
            }
            locationMapWriter.close();
            locationMapWriter.flush();
        } catch (Exception ex) {
            printError(Arrays.toString(ex.getStackTrace()));
        }
    }

    private void processTracesWithoutAnalysis() {
        this.writer.println("=== END OF TRACE ===");
        this.writer.println("Total number of traces: " + traceDB.size());
    }

    private void processTracesWithAnalysis() {
        this.writer.println("=== END OF TRACE ===");
        this.writer.println("Total number of traces: " + traceDB.size());
        this.writer.println("Total number of unique traces: " + traceDB.uniqueTraces());
    }

    private void printError(String message) {
        try {
            FileWriter fileWriter = new FileWriter(System.getenv("TRACEDB_PATH") + TraceDatabase.getInstance().randomFileName + File.separator +
                    "error-location.txt");
            PrintWriter writer = new PrintWriter(fileWriter);
            writer.println("MESSAGE:");
            writer.println(message);
            writer.flush();
            writer.close();
        } catch (Exception ignored) {}
    }

}
