package io.infinity.core.alert;

public enum AlertStatus {
    OPEN,
    ACKNOWLEDGED,
    CLOSED;

    public boolean canMoveTo(AlertStatus target) {
        return target.ordinal() >= ordinal();
    }
}
