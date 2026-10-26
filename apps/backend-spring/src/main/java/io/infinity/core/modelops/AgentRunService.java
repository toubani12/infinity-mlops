package io.infinity.core.modelops;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import io.infinity.core.config.ConflictException;
import io.infinity.core.config.NotFoundException;
import java.time.Clock;
import java.util.UUID;
import org.springframework.context.ApplicationEventPublisher;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Sort;
import org.springframework.lang.Nullable;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class AgentRunService {

    private static final Sort NEWEST_FIRST = Sort.by(Sort.Direction.DESC, "startedAt");
    private static final int MAX_PAYLOAD = 16_000;

    private final AgentRunRepository runs;
    private final AgentRunEventRepository events;
    private final AgentCommandSender commands;
    private final ObjectMapper json;
    private final Clock clock;
    private final ApplicationEventPublisher publisher;
    private final AgentProperties properties;

    public AgentRunService(AgentRunRepository runs, AgentRunEventRepository events, AgentCommandSender commands,
            ObjectMapper json, Clock clock, ApplicationEventPublisher publisher, AgentProperties properties) {
        this.runs = runs;
        this.events = events;
        this.commands = commands;
        this.json = json;
        this.clock = clock;
        this.publisher = publisher;
        this.properties = properties;
    }

    /** Idempotent on event_id, so a redelivered agent.events record changes nothing. */
    @Transactional
    public boolean record(AgentStepEvent step) {
        if (events.existsById(step.eventId())) {
            return false;
        }
        AgentRun run = runs.findById(step.runId()).orElseGet(() -> new AgentRun(step.runId(), step.timestamp()));
        int seq = run.apply(step);
        runs.save(run);
        AgentRunEvent saved = events.save(new AgentRunEvent(step, seq, payloadText(step), clock.instant()));
        publisher.publishEvent(
                new AgentRunChangedEvent(AgentRunResponse.from(run), AgentRunEventResponse.from(saved)));
        return true;
    }

    @Transactional(readOnly = true)
    public Page<AgentRun> list(@Nullable AgentRunStatus status, int page, int size) {
        PageRequest pageable = PageRequest.of(page, size, NEWEST_FIRST);
        return status == null ? runs.findAll(pageable) : runs.findByStatus(status, pageable);
    }

    @Transactional(readOnly = true)
    public AgentRunDetailResponse detail(UUID runId) {
        return AgentRunDetailResponse.from(find(runId), events.findByRunIdOrderBySeqAsc(runId),
                properties.maxP95LatencyMs());
    }

    /**
     * The row is flushed with its new version before the send, so a concurrent decision on the same run waits on the
     * row lock and then fails the version check instead of sending a second command.
     */
    @Transactional
    public AgentRun decide(UUID runId, AgentCommand.Action action, String actor, @Nullable String reason) {
        AgentRun run = find(runId);
        if (run.getStatus() != AgentRunStatus.AWAITING_APPROVAL) {
            throw new ConflictException("Run " + runId + " is " + run.getStatus() + ", not awaiting approval");
        }
        if (run.getPendingCommand() != null) {
            throw new ConflictException("A decision was already sent for run " + runId);
        }
        AgentCommand command = new AgentCommand(runId, UUID.randomUUID(), clock.instant(), action, actor, reason);
        run.commandSent(new PendingCommand(
                command.commandId(), action.wireName(), actor, reason, command.timestamp()));
        runs.saveAndFlush(run);
        commands.send(command);
        publisher.publishEvent(new AgentRunChangedEvent(AgentRunResponse.from(run), null));
        return run;
    }

    private AgentRun find(UUID runId) {
        return runs.findById(runId).orElseThrow(() -> new NotFoundException("Agent run " + runId + " not found"));
    }

    private String payloadText(AgentStepEvent step) {
        try {
            String text = json.writeValueAsString(step.payload());
            return text.length() <= MAX_PAYLOAD ? text : "{\"truncated\":true}";
        } catch (JsonProcessingException e) {
            return "{}";
        }
    }
}
