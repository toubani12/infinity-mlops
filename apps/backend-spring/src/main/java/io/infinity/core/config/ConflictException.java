package io.infinity.core.config;

import org.springframework.http.HttpStatus;
import org.springframework.http.ProblemDetail;
import org.springframework.web.ErrorResponseException;

public class ConflictException extends ErrorResponseException {

    public ConflictException(String detail) {
        super(HttpStatus.CONFLICT, ProblemDetail.forStatusAndDetail(HttpStatus.CONFLICT, detail), null);
    }
}
