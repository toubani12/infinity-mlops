"use client";

import { useApiResource } from "@/hooks/useApiResource";
import { modelsApi } from "@/lib/api";
import { useSession } from "@/lib/auth";
import { ModelBadge } from "./ModelBadge";

function LoadedChampionBadge() {
  const latest = useApiResource("champion", (token, signal) => modelsApi.versions({ size: 1 }, { token, signal }));
  const event = latest.state === "ready" ? latest.data.content[0] : undefined;
  return <ModelBadge modelName={event?.modelName} version={event?.version ?? null} />;
}

export function ChampionBadge() {
  const { session } = useSession();
  return session ? <LoadedChampionBadge /> : <ModelBadge version={null} />;
}
