"use client";

import { BookOpen, Crown, FlaskConical, Gem, ScrollText, Swords } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import * as React from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Logo } from "@/components/layout/logo";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { keys, useGroups, useMe } from "@/lib/queries";
import { useToast } from "@/components/common/misc";

export default function Home() {
  const me = useMe();
  const groups = useGroups(!!me.data);
  const router = useRouter();

  React.useEffect(() => {
    if (!me.data || !groups.data) return;
    let last: string | null = null;
    try {
      last = localStorage.getItem("ac:lastGroup");
    } catch {
      /* ignore */
    }
    const target = groups.data.find((g) => g.id === last) ?? groups.data[0];
    router.replace(target ? `/g/${target.id}` : "/groups/new");
  }, [me.data, groups.data, router]);

  if (me.isLoading || me.data) return <div className="min-h-dvh" />;
  return <Landing />;
}

function Landing() {
  const router = useRouter();
  const qc = useQueryClient();
  const toast = useToast();
  const [demo, setDemo] = React.useState<{ available: boolean } | null>(null);
  React.useEffect(() => {
    api<{ available: boolean }>("/demo/status").then(setDemo).catch(() => setDemo(null));
  }, []);
  const enterDemo = async () => {
    try {
      await api("/demo/login", { method: "POST" });
      await qc.invalidateQueries({ queryKey: keys.me });
      router.push("/");
    } catch (e) {
      toast((e as Error).message, "error");
    }
  };
  const features = [
    { icon: ScrollText, title: "A shared timeline", text: "Boss kills, achievements, loot and memories in one chronological journal." },
    { icon: Swords, title: "Captured, not invented", text: "Addon and Battle.net data with clear provenance — recorded, never guessed." },
    { icon: Gem, title: "The Loot Museum", text: "Every legendary, mount and wishlist drop your group has celebrated." },
    { icon: Crown, title: "Hall of Fame", text: "Reproducible awards and friendly rivalries, week after week, season after season." },
  ];
  return (
    <div className="relative min-h-dvh overflow-hidden">
      <div className="absolute inset-0 -z-10 bg-[radial-gradient(60%_50%_at_50%_0%,rgb(214_169_74/0.18),transparent_70%)]" />
      <header className="mx-auto flex max-w-6xl items-center justify-between px-6 py-5">
        <span className="flex items-center gap-2.5">
          <Logo />
          <span className="font-display text-lg font-bold gold-text">Azeroth Chronicles</span>
        </span>
        <div className="flex gap-2">
          <Button variant="ghost" asChild>
            <Link href="/login">Sign in</Link>
          </Button>
          <Button asChild className="hidden sm:inline-flex">
            <Link href="/register">Create account</Link>
          </Button>
        </div>
      </header>
      <section className="mx-auto max-w-4xl px-6 pb-12 pt-14 text-center sm:pt-24">
        <p className="ornament-divider mx-auto max-w-xs text-xs uppercase tracking-[0.3em]">Est. by your party</p>
        <h1 className="mt-6 text-4xl font-bold leading-tight sm:text-6xl">
          <span className="gold-text">Every adventure,</span>
          <br />
          remembered together.
        </h1>
        <p className="mx-auto mt-6 max-w-2xl text-base text-muted-foreground sm:text-lg">
          A private journal and Hall of Fame for friends who play World of Warcraft together — across guilds, seasons and expansions.
        </p>
        <div className="mt-9 flex flex-col items-center justify-center gap-3 sm:flex-row">
          <Button size="lg" asChild>
            <Link href="/register">
              <BookOpen /> Start your chronicle
            </Link>
          </Button>
          {demo?.available ? (
            <Button size="lg" variant="outline" onClick={enterDemo} data-testid="enter-demo">
              <FlaskConical /> Explore the demo group
            </Button>
          ) : null}
        </div>
        {demo?.available ? <p className="mt-3 text-xs text-muted-foreground">The demo group and everyone in it are fictional.</p> : null}
      </section>
      <section className="mx-auto grid max-w-6xl gap-4 px-6 pb-20 sm:grid-cols-2 lg:grid-cols-4">
        {features.map(({ icon: Icon, title, text }, i) => (
          <div key={title} className="animate-rise rounded-xl border bg-card/70 p-5 parchment" style={{ animationDelay: `${i * 80}ms` }}>
            <Icon className="size-6 text-gold" />
            <h3 className="mt-3 font-display text-base">{title}</h3>
            <p className="mt-1.5 text-sm text-muted-foreground">{text}</p>
          </div>
        ))}
      </section>
      <footer className="pb-8 text-center text-xs text-muted-foreground">
        Not affiliated with Blizzard Entertainment. World of Warcraft is a trademark of Blizzard Entertainment, Inc. ·{" "}
        <Link href="/privacy" className="underline-offset-2 hover:underline">
          Privacy
        </Link>
      </footer>
    </div>
  );
}
