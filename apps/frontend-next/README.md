# frontend-next

Analyst dashboard of Infinity MLOps: transactions, alerts, drift reports, champion history and the agent approval screen.

Next.js 16 (App Router, Cache Components), TypeScript, Tailwind CSS 4, IBM Plex served from `@fontsource` so builds need no font download.

## Layout

| Path | Content |
|---|---|
| `src/app/login` | dev sign-in: calls `POST /api/auth/dev-token` (backend profile `local`) |
| `src/app/(dashboard)/{transactions,alerts,drift,models,agent}` | one route per section; the page is a server component, the live part a client component |
| `src/components` | shell (sidebar, champion badge, session menu), live tables, drift and model views |
| `src/hooks` | `useEventStream` (SSE with exponential backoff), `useApiResource` (token-aware fetch) |
| `src/lib/auth` | session in memory and `sessionStorage` (per tab), cleared on 401 or expiry |
| `src/lib/api` | typed client: `apiFetch`, `ApiError`, endpoint helpers, REST DTOs (`types.ts`) and Kafka contract types (`events.ts`) |

The client reads `NEXT_PUBLIC_API_BASE_URL` (default `http://localhost:8080`). Next.js inlines `NEXT_PUBLIC_*` values at build time, so the Docker image takes it as a build argument. Errors from the backend arrive as problem details and are thrown as `ApiError` with `status` and the parsed `problem`.

Live data: the Transactions page loads the latest 100 rows, then merges `transaction` events from `/api/stream/transactions`; the Alerts page does the same with `/api/stream/alerts` and sends `PATCH /api/alerts/{id}` for Acknowledge and Close. The token goes in the `Authorization` header for REST and in `?access_token=` for SSE, because `EventSource` cannot set headers. On error the stream is closed and reopened after 1, 2, 4 ... 30 s.

## Run and test

```bash
npm ci
npm run dev        # http://localhost:3000
npm run lint
npm test           # vitest + testing-library; npm run test:coverage for a report
npm run build
docker build --build-arg NEXT_PUBLIC_API_BASE_URL=http://localhost:8080 -t frontend-next .
```
