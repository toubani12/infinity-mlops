package io.infinity.core.stream;

import io.micrometer.core.instrument.Gauge;
import io.micrometer.core.instrument.MeterRegistry;
import java.io.IOException;
import java.util.EnumMap;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.CopyOnWriteArraySet;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.function.Supplier;
import org.springframework.beans.factory.DisposableBean;
import org.springframework.context.event.ContextClosedEvent;
import org.springframework.context.event.EventListener;
import org.springframework.http.MediaType;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter.SseEventBuilder;

/**
 * Fans events out to connected dashboards. Sends run on one dedicated thread so a slow client never blocks the
 * Kafka consumer, and events keep their order.
 */
@Component
public class SseBroadcaster implements DisposableBean {

    private final Map<StreamChannel, Set<SseEmitter>> subscribers = new EnumMap<>(StreamChannel.class);
    private final ExecutorService sender =
            Executors.newSingleThreadExecutor(Thread.ofPlatform().name("sse-sender").daemon().factory());
    private final StreamProperties properties;

    public SseBroadcaster(StreamProperties properties, MeterRegistry meters) {
        this.properties = properties;
        for (StreamChannel channel : StreamChannel.values()) {
            Set<SseEmitter> emitters = new CopyOnWriteArraySet<>();
            subscribers.put(channel, emitters);
            Gauge.builder("infinity.sse.clients", emitters, Set::size).tag("channel", channel.name().toLowerCase())
                    .register(meters);
        }
    }

    public SseEmitter subscribe(StreamChannel channel) {
        Set<SseEmitter> emitters = subscribers.get(channel);
        SseEmitter emitter = new SseEmitter(properties.timeout().toMillis());
        emitter.onCompletion(() -> emitters.remove(emitter));
        emitter.onTimeout(emitter::complete);
        emitter.onError(error -> emitters.remove(emitter));
        emitters.add(emitter);
        long reconnectMs = properties.reconnect().toMillis();
        send(emitters, emitter, () -> SseEmitter.event().comment("connected").reconnectTime(reconnectMs));
        return emitter;
    }

    public void publish(StreamChannel channel, String eventName, String id, Object data) {
        Set<SseEmitter> emitters = subscribers.get(channel);
        sender.execute(() -> emitters.forEach(emitter -> send(emitters, emitter,
                () -> SseEmitter.event().name(eventName).id(id).data(data, MediaType.APPLICATION_JSON))));
    }

    public int subscriberCount(StreamChannel channel) {
        return subscribers.get(channel).size();
    }

    @Scheduled(fixedDelayString = "${infinity.stream.heartbeat-ms:15000}")
    void heartbeat() {
        sender.execute(() -> subscribers.values().forEach(emitters -> emitters.forEach(
                emitter -> send(emitters, emitter, () -> SseEmitter.event().comment("heartbeat")))));
    }

    /** Open streams would otherwise hold graceful shutdown for its whole timeout; clients reconnect elsewhere. */
    @EventListener(ContextClosedEvent.class)
    public void closeStreams() {
        subscribers.values().forEach(emitters -> emitters.forEach(SseEmitter::complete));
    }

    @Override
    public void destroy() {
        sender.shutdownNow();
        closeStreams();
    }

    private static void send(Set<SseEmitter> emitters, SseEmitter emitter, Supplier<SseEventBuilder> event) {
        try {
            emitter.send(event.get());
        } catch (IOException | IllegalStateException e) {
            emitters.remove(emitter);
        }
    }
}
