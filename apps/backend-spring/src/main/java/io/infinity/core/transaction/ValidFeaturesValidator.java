package io.infinity.core.transaction;

import jakarta.validation.ConstraintValidator;
import jakarta.validation.ConstraintValidatorContext;
import java.util.HashSet;
import java.util.Map;

public class ValidFeaturesValidator implements ConstraintValidator<ValidFeatures, Map<String, Double>> {

    @Override
    public boolean isValid(Map<String, Double> features, ConstraintValidatorContext context) {
        if (features == null) {
            return true;
        }
        if (!new HashSet<>(Features.NAMES).equals(features.keySet())) {
            return false;
        }
        return features.values().stream().allMatch(v -> v != null && Double.isFinite(v));
    }
}
