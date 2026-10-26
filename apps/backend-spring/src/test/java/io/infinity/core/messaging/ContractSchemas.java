package io.infinity.core.messaging;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.networknt.schema.JsonSchema;
import com.networknt.schema.JsonSchemaFactory;
import com.networknt.schema.SchemaValidatorsConfig;
import com.networknt.schema.SpecVersion;
import com.networknt.schema.ValidationMessage;
import java.io.IOException;
import java.io.InputStream;
import java.io.UncheckedIOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Set;

/** Reads the shared contracts from the monorepo; override the location with -Dcontracts.dir. */
public final class ContractSchemas {

    static final Path CONTRACTS_DIR = Path.of(System.getProperty("contracts.dir", "../../libs/contracts"));

    private static final ObjectMapper JSON = new ObjectMapper();
    private static final SchemaValidatorsConfig CONFIG =
            SchemaValidatorsConfig.builder().formatAssertionsEnabled(true).build();

    private ContractSchemas() {
    }

    public static Set<ValidationMessage> validate(String topic, String payload) {
        try {
            return schema(topic).validate(JSON.readTree(payload));
        } catch (IOException e) {
            throw new UncheckedIOException(e);
        }
    }

    public static String example(String topic) {
        try {
            return Files.readString(CONTRACTS_DIR.resolve("examples").resolve(topic + ".v1.json"));
        } catch (IOException e) {
            throw new UncheckedIOException(e);
        }
    }

    public static JsonNode readTree(String payload) {
        try {
            return JSON.readTree(payload);
        } catch (IOException e) {
            throw new UncheckedIOException(e);
        }
    }

    private static JsonSchema schema(String topic) throws IOException {
        Path file = CONTRACTS_DIR.resolve("events").resolve(topic + ".v1.json");
        try (InputStream in = Files.newInputStream(file)) {
            return JsonSchemaFactory.getInstance(SpecVersion.VersionFlag.V202012).getSchema(in, CONFIG);
        }
    }
}
