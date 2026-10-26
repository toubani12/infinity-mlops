package io.infinity.core.transaction;

import jakarta.validation.Constraint;
import jakarta.validation.Payload;
import java.lang.annotation.ElementType;
import java.lang.annotation.Retention;
import java.lang.annotation.RetentionPolicy;
import java.lang.annotation.Target;

@Target({ElementType.FIELD, ElementType.RECORD_COMPONENT, ElementType.PARAMETER})
@Retention(RetentionPolicy.RUNTIME)
@Constraint(validatedBy = ValidFeaturesValidator.class)
public @interface ValidFeatures {

    String message() default "must contain exactly the finite numeric features v1 to v28";

    Class<?>[] groups() default {};

    Class<? extends Payload>[] payload() default {};
}
