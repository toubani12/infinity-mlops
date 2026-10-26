-- POSTGRES_DB creates "infinity"; MLflow and the LangGraph checkpointer get their own databases.
CREATE DATABASE mlflow;
CREATE DATABASE agent;
