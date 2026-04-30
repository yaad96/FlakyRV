package com.runtimeverification.rvmonitor.java.rt.observable;

import com.runtimeverification.rvmonitor.java.rt.util.TraceDatabase;

import java.io.File;
import java.io.FileWriter;
import java.io.PrintWriter;
import java.text.DecimalFormat;
import java.util.*;

public class UniqueMonitorTraceCollector extends AllMonitorTraceCollector {

    private PrintWriter uniqueWriter;

    List<Integer> frequencies = new ArrayList<>();
    List<Integer> lengths = new ArrayList<>();

    public UniqueMonitorTraceCollector(PrintWriter writer, boolean doAnalysis, boolean writeLocationMap,
                                       File locationMapFile, String dbPath, String dbConfigFile,
                                       PrintWriter uniqueWriter) {
        super(writer, doAnalysis, writeLocationMap, locationMapFile, dbPath, dbConfigFile);
        this.uniqueWriter = uniqueWriter;
    }

    @Override
    public void onCompleted() {
        super.onCompleted();
        if (isDoAnalysis()) {
            analyzeUniqueTraces();
        }
        if (isDumpingTraces()) {
            traceDB.dump();
        }
    }

    private String getFrequencyMap(Map<String, Integer> traceFrequencyMap) {
        StringBuilder builder = new StringBuilder();
        for (Map.Entry<String, Integer> entry : traceFrequencyMap.entrySet()) {
            builder.append(entry.getValue() + " " + entry.getKey() + "\n");
            frequencies.add(entry.getValue());
        }
        return builder.toString();
    }

    private void analyzeUniqueTraces() {
        try {
            int i = 0;
            uniqueWriter.println("=== UNIQUE TRACES ===");
            for (Map.Entry<String, Integer> entry : traceDB.getTraceFrequencies().entrySet()) {
                uniqueWriter.println(entry.getValue() + " " + entry.getKey());
                i++;

                if (i % 10 == 0) {
                    uniqueWriter.flush();
                }
            }
//        uniqueWriter.println("=== UNIQUE TRACE STATS ===");
//        if (traceDB.size() == 0) return; // prevent IndexOutOfBoundsException when TraceDB is empty
//        DecimalFormat format = new DecimalFormat("0.00");
//        lengths = traceDB.getTraceLengths();
//        Collections.sort(lengths);
//        uniqueWriter.println("Min Trace Size: " + lengths.get(0));
//        uniqueWriter.println("Max Trace Size: " + lengths.get(lengths.size() -1 ));
//        uniqueWriter.println("Average Trace Size: " + format.format(average(lengths)));
//        String frequencyString = getFrequencyMap(traceDB.getTraceFrequencies());
//        Collections.sort(frequencies);
//        uniqueWriter.println("Min Trace Frequency: " + frequencies.get(0));
//        uniqueWriter.println("Max Trace Frequency: " + frequencies.get(frequencies.size() -1 ));
//        uniqueWriter.println("Average Trace Frequency: " + format.format(average(frequencies)));
//        uniqueWriter.println("=== END UNIQUE TRACE STATS ===");
//        uniqueWriter.println("=== UNIQUE TRACES ===");
//        uniqueWriter.println(frequencyString);
            uniqueWriter.flush();
            if (uniqueWriter.checkError()) {
                uniqueWriter.println("There was an error!");
                uniqueWriter.flush();
            }
            uniqueWriter.close();
        } catch (Exception ex) {
            printError(ex + "\n" + Arrays.toString(ex.getStackTrace()));
        }
    }

    private double average(List<Integer> uniqueDepths) {
        double sum = 0.0;
        for (int depth : uniqueDepths) {
            sum += depth;
        }
        return sum / uniqueDepths.size();
    }

    private void printError(String message) {
        try {
            FileWriter fileWriter = new FileWriter(System.getenv("TRACEDB_PATH") + TraceDatabase.getInstance().randomFileName + File.separator +
                    "error-unique-traces.txt");
            PrintWriter writer = new PrintWriter(fileWriter);
            writer.println(message);
            writer.flush();
            writer.close();
        } catch (Exception ignored) {}
    }
}

