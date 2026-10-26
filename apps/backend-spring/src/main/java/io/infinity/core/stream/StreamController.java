package io.infinity.core.stream;

import org.springframework.http.MediaType;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

@RestController
@RequestMapping(path = "/api/stream", produces = MediaType.TEXT_EVENT_STREAM_VALUE)
public class StreamController {

    private final SseBroadcaster broadcaster;

    public StreamController(SseBroadcaster broadcaster) {
        this.broadcaster = broadcaster;
    }

    @GetMapping("/transactions")
    public SseEmitter transactions() {
        return broadcaster.subscribe(StreamChannel.TRANSACTIONS);
    }

    @GetMapping("/alerts")
    public SseEmitter alerts() {
        return broadcaster.subscribe(StreamChannel.ALERTS);
    }
}
