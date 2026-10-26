package io.infinity.core.transaction;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.stream.IntStream;

public final class Features {

    public static final int COUNT = 28;
    public static final List<String> NAMES = IntStream.rangeClosed(1, COUNT).mapToObj(i -> "v" + i).toList();

    private Features() {
    }

    public static double[] toArray(Map<String, Double> features) {
        double[] values = new double[COUNT];
        for (int i = 0; i < COUNT; i++) {
            Double value = features.get(NAMES.get(i));
            if (value == null) {
                throw new IllegalArgumentException("missing feature " + NAMES.get(i));
            }
            values[i] = value;
        }
        return values;
    }

    public static Map<String, Double> toMap(double[] values) {
        if (values.length != COUNT) {
            throw new IllegalArgumentException("expected " + COUNT + " features, got " + values.length);
        }
        Map<String, Double> features = new LinkedHashMap<>();
        for (int i = 0; i < COUNT; i++) {
            features.put(NAMES.get(i), values[i]);
        }
        return features;
    }
}
