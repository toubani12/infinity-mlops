package io.infinity.core.security;

import jakarta.servlet.http.HttpServletRequest;
import org.springframework.security.oauth2.server.resource.web.BearerTokenResolver;
import org.springframework.security.oauth2.server.resource.web.DefaultBearerTokenResolver;

/** EventSource cannot set headers, so SSE endpoints also accept {@code ?access_token=}; nothing else does. */
public class StreamTokenResolver implements BearerTokenResolver {

    static final String STREAM_PREFIX = "/api/stream/";

    private final DefaultBearerTokenResolver headerOnly = new DefaultBearerTokenResolver();
    private final DefaultBearerTokenResolver headerOrQuery = new DefaultBearerTokenResolver();

    public StreamTokenResolver() {
        headerOrQuery.setAllowUriQueryParameter(true);
    }

    @Override
    public String resolve(HttpServletRequest request) {
        String path = request.getRequestURI().substring(request.getContextPath().length());
        return path.startsWith(STREAM_PREFIX) ? headerOrQuery.resolve(request) : headerOnly.resolve(request);
    }
}
