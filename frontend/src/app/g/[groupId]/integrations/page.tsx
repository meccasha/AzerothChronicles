"use client";

import { AlertTriangle, CheckCircle2, CircleDashed, Download, KeyRound, Plug, RefreshCw, Upload, Wand2 } from "lucide-react";
import { useParams, useSearchParams } from "next/navigation";
import * as React from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ErrorState, Notice, PageHeader, useToast } from "@/components/common/misc";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input, Select, Textarea } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/misc";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { api } from "@/lib/api";
import { fmtDateTime, fmtRelative } from "@/lib/format";
import { keys, useIntegrationStatus, useMe, useTokens } from "@/lib/queries";
import type { IngestResult, SourceStatus } from "@/lib/types";

function Status({ src, emptyText }: { src: SourceStatus | null; emptyText: string }) {
  if (!src) return <Badge variant="secondary"><CircleDashed /> {emptyText}</Badge>;
  if (src.status === "ok") return <Badge variant="success"><CheckCircle2 /> Healthy</Badge>;
  if (src.status === "error") return <Badge variant="danger"><AlertTriangle /> Errors</Badge>;
  return <Badge variant="secondary">{src.status}</Badge>;
}

function IntegrationsInner() {
  const { groupId } = useParams<{ groupId: string }>();
  const params = useSearchParams();
  const status = useIntegrationStatus();
  const me = useMe();
  const qc = useQueryClient();
  const toast = useToast();
  const flash = params.get("blizzard");

  React.useEffect(() => {
    if (flash === "linked") toast("Battle.net account linked");
    else if (flash === "denied") toast("Battle.net authorization was cancelled", "error");
    else if (flash === "invalid_state") toast("Link attempt expired or was invalid — please try again", "error");
    else if (flash === "error") toast(params.get("message") ?? "Battle.net linking failed", "error");
  }, [flash, params, toast]);

  if (status.isError) return <ErrorState error={status.error} retry={() => status.refetch()} />;
  if (!status.data) return <Skeleton className="h-96 rounded-xl" />;
  const s = status.data;
  const refresh = () => {
    qc.invalidateQueries({ queryKey: ["integrations"] });
    qc.invalidateQueries({ queryKey: keys.group(groupId) });
    qc.invalidateQueries({ queryKey: ["my-characters"] });
  };

  const link = async () => {
    try {
      const r = await api<{ url: string }>("/integrations/blizzard/authorize?region=" + ((document.getElementById("bnet-region") as HTMLSelectElement)?.value ?? "us"));
      window.location.href = r.url;
    } catch (e) {
      toast((e as Error).message, "error");
    }
  };
  const sync = async () => {
    try {
      await api("/integrations/blizzard/sync", { method: "POST" });
      toast("Sync started");
      setTimeout(refresh, 1500);
    } catch (e) {
      toast((e as Error).message, "error");
    }
  };

  return (
    <div className="flex flex-col gap-6">
      <PageHeader icon={Plug} title="Integrations" subtitle="Where your data comes from, when it last arrived, and what went wrong. Nothing here is real-time: data arrives when a sync or upload happens." />
      {me.data?.is_demo ? <Notice tone="warn">You are browsing as a fictional demo member. Linking and uploads are disabled — create an account to connect your own data.</Notice> : null}

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader className="flex-row items-start justify-between gap-3">
            <div>
              <CardTitle>Battle.net</CardTitle>
              <CardDescription>Verifies character ownership and imports achievements with their real completion dates.</CardDescription>
            </div>
            <Status src={s.blizzard.source} emptyText="Not linked" />
          </CardHeader>
          <CardContent className="flex flex-col gap-4 text-sm">
            {s.blizzard.adapter_mode === "mock" ? (
              <Notice>Development mode: Battle.net is simulated with fictional fixture data (MockHero#1234). Set BLIZZARD_ADAPTER=live with real credentials to connect for real.</Notice>
            ) : null}
            {s.blizzard.linked ? (
              <>
                <p>
                  Linked as <strong className="text-gold-bright">{s.blizzard.battletag}</strong> ({s.blizzard.region?.toUpperCase()})
                </p>
                {s.blizzard.authorization_expired ? <Notice tone="warn">Battle.net authorization has expired. Achievement syncs keep working; re-link to refresh your character list or detect renames.</Notice> : null}
                <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-xs text-muted-foreground">
                  <dt>Last successful sync</dt>
                  <dd>{s.blizzard.source?.last_success_at ? fmtDateTime(s.blizzard.source.last_success_at) : "never"}</dd>
                  <dt>Last attempt</dt>
                  <dd>{s.blizzard.source?.last_attempt_at ? fmtRelative(s.blizzard.source.last_attempt_at) : "never"}</dd>
                </dl>
                {s.blizzard.source?.last_error ? <p className="whitespace-pre-line rounded-md border border-destructive/30 bg-destructive/10 p-2 text-xs text-red-200">{s.blizzard.source.last_error}</p> : null}
                <CharacterPicker onLinked={refresh} />
                <div className="flex flex-wrap gap-2">
                  <Button onClick={sync}>
                    <RefreshCw /> Sync achievements now
                  </Button>
                  <Button variant="outline" onClick={link}>
                    Re-link
                  </Button>
                  <Button variant="ghost" onClick={async () => { if (confirm("Unlink Battle.net? Stored tokens are deleted; your history stays.")) { await api("/integrations/blizzard", { method: "DELETE" }); refresh(); } }}>
                    Unlink
                  </Button>
                </div>
              </>
            ) : (
              <div className="flex flex-wrap items-center gap-2">
                <Select id="bnet-region" defaultValue="us" className="w-28" aria-label="Region">
                  <option value="us">US</option>
                  <option value="eu">EU</option>
                  <option value="kr">KR</option>
                  <option value="tw">TW</option>
                </Select>
                <Button onClick={link} disabled={!s.blizzard.configured || me.data?.is_demo}>
                  Link Battle.net
                </Button>
                {!s.blizzard.configured ? <span className="text-xs text-amber">Server is missing Battle.net credentials.</span> : null}
              </div>
            )}
            <p className="text-xs text-muted-foreground">We use Blizzard&apos;s official OAuth. We never see or store your password. The first sync imports history as a labelled backfill; only later syncs create &quot;new&quot; achievements.</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex-row items-start justify-between gap-3">
            <div>
              <CardTitle>AzerothChronicles addon</CardTitle>
              <CardDescription>Records boss pulls, wipes, notable loot, mounts and achievements in-game.</CardDescription>
            </div>
            <Status src={s.addon.source} emptyText="No uploads yet" />
          </CardHeader>
          <CardContent className="flex flex-col gap-3 text-sm">
            <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-xs text-muted-foreground">
              <dt>Last successful upload</dt>
              <dd>{s.addon.source?.last_success_at ? fmtDateTime(s.addon.source.last_success_at) : "never"}</dd>
              <dt>Addon version</dt>
              <dd>{String(s.addon.source?.details?.addon_version ?? "–")}</dd>
              <dt>Companion tokens</dt>
              <dd>{s.addon.active_tokens} active</dd>
            </dl>
            <ol className="list-decimal space-y-1 pl-5 text-xs text-muted-foreground">
              <li>Install the addon from <code>addon/AzerothChronicles</code> into <code>_retail_/Interface/AddOns/</code>.</li>
              <li>Play! Type <code>/achron</code> in-game to see what has been recorded.</li>
              <li>After logging out (SavedVariables are written on logout/reload), upload below — or run the companion app for automatic uploads.</li>
            </ol>
            <Notice>WoW addons cannot talk to the internet. Data reaches us only when you upload it or when the companion app notices the SavedVariables file changed.</Notice>
          </CardContent>
        </Card>
      </div>

      <ImportCard groupId={groupId} disabled={!!me.data?.is_demo} onDone={refresh} />
      <TokensCard disabled={!!me.data?.is_demo} />

      <Card>
        <CardHeader>
          <CardTitle>Recent sync jobs &amp; ingestion errors</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-6 lg:grid-cols-2">
          <ul className="flex flex-col gap-2 text-xs">
            {s.jobs.length ? (
              s.jobs.map((j) => (
                <li key={j.id} className="rounded-md border px-3 py-2">
                  <div className="flex items-center gap-2">
                    <Badge variant={j.status === "succeeded" ? "success" : j.status === "failed" ? "danger" : j.status === "partial" ? "warning" : "secondary"}>{j.status}</Badge>
                    <span className="font-medium">{j.kind.replaceAll("_", " ")}</span>
                    <span className="ml-auto text-muted-foreground">{j.started_at ? fmtRelative(j.started_at) : ""}</span>
                  </div>
                  <p className="mt-1 text-muted-foreground">
                    {Object.entries(j.stats)
                      .filter(([, v]) => typeof v === "number" && v)
                      .map(([k, v]) => `${k.replaceAll("_", " ")}: ${v}`)
                      .join(" · ") || "no changes"}
                  </p>
                  {j.error ? <p className="mt-1 whitespace-pre-line text-red-300">{j.error}</p> : null}
                </li>
              ))
            ) : (
              <li className="text-muted-foreground">No jobs yet.</li>
            )}
          </ul>
          <ul className="flex flex-col gap-2 text-xs">
            {s.recent_errors.length ? (
              s.recent_errors.map((e) => (
                <li key={e.id} className="rounded-md border border-destructive/30 bg-destructive/5 px-3 py-2">
                  <span className="font-medium">{e.record_type}</span> <span className="text-muted-foreground">· {fmtRelative(e.received_at)}</span>
                  <p className="text-red-200">{e.detail}</p>
                </li>
              ))
            ) : (
              <li className="flex items-center gap-2 text-muted-foreground">
                <CheckCircle2 className="size-4 text-emerald-400" /> No rejected records.
              </li>
            )}
          </ul>
        </CardContent>
      </Card>
    </div>
  );
}

function CharacterPicker({ onLinked }: { onLinked: () => void }) {
  const toast = useToast();
  const chars = useQuery({
    queryKey: ["bnet-characters"],
    queryFn: () => api<{ blizzard_id: number; name: string; realm_name: string; level: number | null; character_class: string | null; linked: boolean }[]>("/integrations/blizzard/account-characters"),
    retry: false,
  });
  const [sel, setSel] = React.useState<number[]>([]);
  if (chars.isError) return <p className="text-xs text-amber">{(chars.error as Error).message}</p>;
  if (!chars.data) return <Skeleton className="h-20" />;
  const link = async () => {
    try {
      await api("/integrations/blizzard/characters", { method: "POST", json: { blizzard_ids: sel } });
      toast("Characters linked — first sync started");
      setSel([]);
      chars.refetch();
      setTimeout(onLinked, 1500);
    } catch (e) {
      toast((e as Error).message, "error");
    }
  };
  return (
    <div className="rounded-lg border bg-background-2/50 p-3">
      <p className="mb-2 text-xs uppercase tracking-wider text-muted-foreground">Characters on this Battle.net account</p>
      <ul className="max-h-48 overflow-y-auto">
        {chars.data.map((c) => (
          <li key={c.blizzard_id}>
            <label className="flex items-center gap-2 py-1 text-sm">
              <input type="checkbox" disabled={c.linked} checked={c.linked || sel.includes(c.blizzard_id)} onChange={(e) => setSel((s) => (e.target.checked ? [...s, c.blizzard_id] : s.filter((x) => x !== c.blizzard_id)))} className="accent-[var(--gold)]" />
              <span className="flex-1">
                {c.name} <span className="text-xs text-muted-foreground">· {c.realm_name} · {c.level ? `Lv ${c.level} ` : ""}{c.character_class}</span>
              </span>
              {c.linked ? <Badge variant="success">linked</Badge> : null}
            </label>
          </li>
        ))}
      </ul>
      <Button size="sm" className="mt-2" disabled={!sel.length} onClick={link}>
        Link selected
      </Button>
    </div>
  );
}

function ImportCard({ groupId, disabled, onDone }: { groupId: string; disabled: boolean; onDone: () => void }) {
  const toast = useToast();
  const [text, setText] = React.useState("");
  const [result, setResult] = React.useState<IngestResult | null>(null);
  const [busy, setBusy] = React.useState(false);
  const run = async (fn: () => Promise<IngestResult>) => {
    setBusy(true);
    try {
      const r = await fn();
      setResult(r);
      toast(`Imported: ${r.normalized} new, ${r.duplicates} duplicates`);
      onDone();
    } catch (e) {
      toast((e as Error).message, "error");
    } finally {
      setBusy(false);
    }
  };
  const uploadFile = (file: File) =>
    run(async () => api<IngestResult>("/ingest/savedvariables", { method: "POST", body: await file.text(), headers: { "content-type": "text/plain" } }));
  const importText = () =>
    run(() => {
      const t = text.trim();
      if (t.startsWith("{")) return api<IngestResult>("/ingest/envelope", { method: "POST", body: t, headers: { "content-type": "application/json" } });
      return api<IngestResult>("/ingest/savedvariables", { method: "POST", body: t, headers: { "content-type": "text/plain" } });
    });
  const loadSample = async () => {
    const sample = await api<Record<string, unknown>>(`/ingest/sample?group_id=${groupId}`);
    setText(JSON.stringify(sample, null, 2));
  };
  return (
    <Card>
      <CardHeader>
        <CardTitle>Import game data</CardTitle>
        <CardDescription>Uploads are idempotent: importing the same file twice never creates duplicates.</CardDescription>
      </CardHeader>
      <CardContent>
        <Tabs defaultValue="file">
          <TabsList>
            <TabsTrigger value="file">
              <Upload className="size-3.5" /> SavedVariables file
            </TabsTrigger>
            <TabsTrigger value="paste">Paste export / JSON</TabsTrigger>
          </TabsList>
          <TabsContent value="file" className="mt-4 flex flex-col gap-2 text-sm">
            <p className="text-muted-foreground">
              Choose <code className="text-xs">WTF/Account/&lt;ACCOUNT&gt;/SavedVariables/AzerothChronicles.lua</code>. It is parsed as data — never executed.
            </p>
            <Input type="file" accept=".lua,text/plain" disabled={disabled || busy} onChange={(e) => e.target.files?.[0] && uploadFile(e.target.files[0])} className="h-auto max-w-md py-1.5" aria-label="SavedVariables file" />
          </TabsContent>
          <TabsContent value="paste" className="mt-4 flex flex-col gap-2">
            <Textarea value={text} onChange={(e) => setText(e.target.value)} rows={10} className="font-mono text-xs" placeholder='Paste the in-game export (/achron export) or a normalized JSON envelope {"format": "azeroth-chronicles/v1", ...}' aria-label="Import data" />
            <div className="flex flex-wrap gap-2">
              <Button onClick={importText} disabled={disabled || busy || !text.trim()}>
                <Download /> Import
              </Button>
              <Button variant="outline" onClick={loadSample} disabled={disabled} data-testid="load-sample">
                <Wand2 /> Generate simulated events
              </Button>
            </div>
            <p className="text-xs text-muted-foreground">Simulated events are marked &quot;Simulated import&quot; on the timeline. Edit them freely before importing.</p>
          </TabsContent>
        </Tabs>
        {result ? (
          <div className="mt-4 rounded-lg border bg-background-2/60 p-3 text-xs" data-testid="import-result">
            <p className="font-medium text-foreground">
              Received {result.received}: {result.normalized} normalized · {result.duplicates} duplicates · {result.ignored} ignored · {result.rejected} rejected
            </p>
            <p className="text-muted-foreground">
              Timeline: {result.events_created} new events, {result.events_merged} merged into existing events{result.groups.length ? ` (${result.groups.join(", ")})` : ""}
            </p>
            {result.messages.map((m) => (
              <p key={m} className="text-amber">{m}</p>
            ))}
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}

function TokensCard({ disabled }: { disabled: boolean }) {
  const tokens = useTokens();
  const qc = useQueryClient();
  const [created, setCreated] = React.useState<string | null>(null);
  const [name, setName] = React.useState("Companion app");
  const create = async () => {
    const r = await api<{ token: string }>("/me/tokens", { method: "POST", json: { name } });
    setCreated(r.token);
    qc.invalidateQueries({ queryKey: ["tokens"] });
  };
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <KeyRound className="size-4 text-gold" /> Companion upload tokens
        </CardTitle>
        <CardDescription>The optional companion app watches your SavedVariables file and uploads it after you log out. Tokens can only upload data.</CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-3 text-sm">
        <div className="flex flex-wrap gap-2">
          <Input value={name} onChange={(e) => setName(e.target.value)} className="max-w-xs" aria-label="Token name" />
          <Button variant="outline" onClick={create} disabled={disabled || !name}>
            Create token
          </Button>
        </div>
        {created ? (
          <Notice tone="warn">
            Copy this token now — it won&apos;t be shown again: <code className="break-all font-mono text-foreground">{created}</code>
          </Notice>
        ) : null}
        <ul className="flex flex-col gap-1.5">
          {tokens.data?.map((t) => (
            <li key={t.id} className="flex flex-wrap items-center gap-2 rounded-md border px-3 py-1.5 text-xs">
              <span className="font-medium">{t.name}</span>
              <code className="text-muted-foreground">{t.token_prefix}…</code>
              <span className="text-muted-foreground">last used {t.last_used_at ? fmtRelative(t.last_used_at) : "never"}</span>
              {t.revoked_at ? (
                <Badge variant="secondary" className="ml-auto">revoked</Badge>
              ) : (
                <Button size="sm" variant="ghost" className="ml-auto" onClick={async () => { await api(`/me/tokens/${t.id}`, { method: "DELETE" }); qc.invalidateQueries({ queryKey: ["tokens"] }); }}>
                  Revoke
                </Button>
              )}
            </li>
          ))}
        </ul>
      </CardContent>
    </Card>
  );
}

export default function IntegrationsPage() {
  return (
    <React.Suspense>
      <IntegrationsInner />
    </React.Suspense>
  );
}
