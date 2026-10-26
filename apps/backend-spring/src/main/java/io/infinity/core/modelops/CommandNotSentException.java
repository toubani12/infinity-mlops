package io.infinity.core.modelops;

import org.springframework.http.HttpStatus;
import org.springframework.http.ProblemDetail;
import org.springframework.web.ErrorResponseException;

public class CommandNotSentException extends ErrorResponseException {

    public CommandNotSentException(Throwable cause) {
        super(HttpStatus.SERVICE_UNAVAILABLE, ProblemDetail.forStatusAndDetail(HttpStatus.SERVICE_UNAVAILABLE,
                "The decision could not be delivered to the agent, nothing was changed. Try again."), cause);
    }
}
