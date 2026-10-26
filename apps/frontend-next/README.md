# frontend-next

Analyst dashboard of Infinity MLOps: transactions, alerts, drift reports, champion history and the agent approval screen.

Next.js 16 (App Router, Cache Components), TypeScript, Tailwind CSS 4, IBM Plex served from `@fontsource` so builds need no font download.

## Layout

| Path | Content |
|---|---|
| `src/app/(dashboard)/{transactions,alerts,drift,models,agent}` | one route per section, server components by default |
| `src/components` | shell (sidebar, model badge, page header, empty state) |
| `src/lib/api` | typed client: `apiFetch`, `ApiError`, endpoint helpers, REST DTOs (`types.ts`) and Kafka contract types (`events.ts`) |

The client reads `NEXT_PUBLIC_API_BASE_URL` (default `http://localhost:8080`). Next.js inlines `NEXT_PUBLIC_*` values at build time, so the Docker image takes it as a build argument. Errors from the backend arrive as problem details and are thrown as `ApiError` with `status` and the parsed `problem`.

## Run and test

```bash
npm ci
npm run dev        # http://localhost:3000
npm run lint
npm test           # vitest + testing-library; npm run test:coverage for a report
npm run build
docker build --build-arg NEXT_PUBLIC_API_BASE_URL=http://localhost:8080 -t frontend-next .
```
