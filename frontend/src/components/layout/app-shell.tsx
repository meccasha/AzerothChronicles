"use client";

import {
  BarChart3,
  ChevronsUpDown,
  Crown,
  FlaskConical,
  Gem,
  LayoutDashboard,
  LogOut,
  Menu,
  Plug,
  Plus,
  ScrollText,
  Settings,
  UserCog,
  Users,
  X,
} from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { DropdownMenu } from "radix-ui";
import * as React from "react";
import { useQueryClient } from "@tanstack/react-query";
import { MemberAvatar } from "@/components/common/avatar";
import { Logo } from "@/components/layout/logo";
import { api } from "@/lib/api";
import { useGroups, useMe } from "@/lib/queries";
import type { Group, User } from "@/lib/types";
import { cn } from "@/lib/utils";

const NAV = [
  { href: "", label: "Dashboard", icon: LayoutDashboard },
  { href: "/timeline", label: "Adventure Timeline", icon: ScrollText },
  { href: "/stats", label: "Group Statistics", icon: BarChart3 },
  { href: "/hall-of-fame", label: "Hall of Fame", icon: Crown },
  { href: "/loot", label: "Loot Museum", icon: Gem },
  { href: "/members", label: "Members", icon: Users },
  { href: "/integrations", label: "Integrations", icon: Plug },
  { href: "/settings", label: "Group Settings", icon: Settings },
];
const MOBILE_NAV = NAV.slice(0, 5);

export function AppShell({ groupId, children }: { groupId: string; children: React.ReactNode }) {
  const me = useMe();
  const groups = useGroups(!!me.data);
  const router = useRouter();
  const pathname = usePathname();
  const [open, setOpen] = React.useState(false);

  React.useEffect(() => {
    if (me.data === null) router.replace(`/login?next=${encodeURIComponent(pathname)}`);
  }, [me.data, router, pathname]);
  React.useEffect(() => setOpen(false), [pathname]);
  React.useEffect(() => {
    try {
      localStorage.setItem("ac:lastGroup", groupId);
    } catch {
      /* storage unavailable */
    }
  }, [groupId]);

  if (!me.data) return <div className="min-h-dvh" />;
  const group = groups.data?.find((g) => g.id === groupId);
  const base = `/g/${groupId}`;
  const isActive = (href: string) => (href === "" ? pathname === base : pathname.startsWith(base + href));

  const nav = (
    <nav className="flex flex-col gap-0.5" aria-label="Main">
      {NAV.map(({ href, label, icon: Icon }) => (
        <Link
          key={href}
          href={base + href}
          className={cn(
            "group flex items-center gap-3 rounded-lg px-3 py-2 text-sm text-muted-foreground transition hover:bg-accent/60 hover:text-foreground",
            isActive(href) && "bg-gradient-to-r from-gold/15 to-transparent text-gold-bright shadow-[inset_2px_0_0_var(--gold)]",
          )}
        >
          <Icon className={cn("size-4 transition", isActive(href) ? "text-gold" : "text-muted-foreground group-hover:text-gold/80")} />
          {label}
        </Link>
      ))}
    </nav>
  );

  return (
    <div className="min-h-dvh lg:grid lg:grid-cols-[260px_1fr]">
      {/* Desktop sidebar */}
      <aside className="sticky top-0 hidden h-dvh flex-col border-r bg-background-2 px-4 py-5 lg:flex">
        <Link href="/" className="mb-6 flex items-center gap-2.5 px-2">
          <Logo />
          <span className="font-display text-lg font-bold leading-tight gold-text">Azeroth Chronicles</span>
        </Link>
        <GroupSwitcher groups={groups.data ?? []} current={group} />
        <div className="mt-5 flex-1 overflow-y-auto">{nav}</div>
        <UserMenu me={me.data} />
      </aside>

      {/* Mobile top bar */}
      <header className="sticky top-0 z-40 flex items-center justify-between gap-3 border-b bg-background/95 px-4 py-2.5 lg:hidden">
        <Link href={base} className="flex min-w-0 items-center gap-2">
          <Logo size={26} />
          <span className="truncate font-display text-sm font-semibold gold-text">{group?.name ?? "Azeroth Chronicles"}</span>
        </Link>
        <button className="rounded-md p-2 hover:bg-accent" onClick={() => setOpen(true)} aria-label="Open menu">
          <Menu className="size-5" />
        </button>
      </header>
      {open ? (
        <div className="fixed inset-0 z-50 lg:hidden" role="dialog" aria-modal="true" aria-label="Menu">
          <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" onClick={() => setOpen(false)} />
          <div className="absolute inset-y-0 right-0 flex w-[85%] max-w-xs animate-in slide-in-from-right flex-col gap-4 border-l bg-background-2 p-4">
            <div className="flex items-center justify-between">
              <span className="font-display gold-text">Menu</span>
              <button className="rounded-md p-2 hover:bg-accent" onClick={() => setOpen(false)} aria-label="Close menu">
                <X className="size-5" />
              </button>
            </div>
            <GroupSwitcher groups={groups.data ?? []} current={group} />
            <div className="flex-1 overflow-y-auto">{nav}</div>
            <UserMenu me={me.data} />
          </div>
        </div>
      ) : null}

      <main className="min-w-0 pb-24 lg:pb-10">
        {group?.is_demo ? (
          <div className="flex items-center justify-center gap-2 border-b border-sky-500/20 bg-sky-500/10 px-4 py-1.5 text-center text-xs text-sky-200">
            <FlaskConical className="size-3.5 shrink-0" /> Demo mode — every member, character, raid and item in this group is fictional.
          </div>
        ) : null}
        <div className="mx-auto w-full max-w-7xl px-4 py-6 sm:px-6 lg:px-10 lg:py-8">{children}</div>
      </main>

      {/* Mobile bottom nav */}
      <nav className="fixed inset-x-0 bottom-0 z-40 grid grid-cols-5 border-t bg-background/95 lg:hidden" aria-label="Quick">
        {MOBILE_NAV.map(({ href, label, icon: Icon }) => (
          <Link key={href} href={base + href} className={cn("flex flex-col items-center gap-0.5 py-2 text-[10px] text-muted-foreground", isActive(href) && "text-gold-bright")}>
            <Icon className="size-5" />
            {label.split(" ").slice(-1)[0]}
          </Link>
        ))}
      </nav>
    </div>
  );
}

function GroupSwitcher({ groups, current }: { groups: Group[]; current?: Group }) {
  return (
    <DropdownMenu.Root>
      <DropdownMenu.Trigger className="flex w-full items-center gap-3 rounded-lg border bg-card/80 px-3 py-2.5 text-left transition hover:border-gold/40 cursor-pointer">
        <span className="flex size-8 shrink-0 items-center justify-center rounded-md bg-gradient-to-br from-gold/30 to-ember/20 font-display text-sm text-gold-bright">
          {current?.name[0] ?? "?"}
        </span>
        <span className="min-w-0 flex-1">
          <span className="block truncate text-sm font-medium">{current?.name ?? "Select a group"}</span>
          <span className="block text-xs capitalize text-muted-foreground">
            {current ? `${current.member_count} members · ${current.my_role}` : " "}
          </span>
        </span>
        <ChevronsUpDown className="size-4 text-muted-foreground" />
      </DropdownMenu.Trigger>
      <DropdownMenu.Portal>
        <DropdownMenu.Content align="start" sideOffset={6} className="z-50 w-64 rounded-lg border border-gold/25 bg-popover p-1 shadow-xl">
          <DropdownMenu.Label className="px-2 py-1.5 text-[11px] uppercase tracking-wider text-muted-foreground">Your groups</DropdownMenu.Label>
          {groups.map((g) => (
            <DropdownMenu.Item key={g.id} asChild>
              <Link href={`/g/${g.id}`} className={cn("flex cursor-pointer items-center gap-2 rounded-md px-2 py-1.5 text-sm outline-none data-[highlighted]:bg-accent", g.id === current?.id && "text-gold-bright")}>
                <span className="truncate">{g.name}</span>
                {g.is_demo ? <span className="ml-auto text-[10px] text-sky-300">demo</span> : null}
              </Link>
            </DropdownMenu.Item>
          ))}
          <DropdownMenu.Separator className="my-1 h-px bg-border" />
          <DropdownMenu.Item asChild>
            <Link href="/groups/new" className="flex cursor-pointer items-center gap-2 rounded-md px-2 py-1.5 text-sm outline-none data-[highlighted]:bg-accent">
              <Plus className="size-4" /> Create a group
            </Link>
          </DropdownMenu.Item>
        </DropdownMenu.Content>
      </DropdownMenu.Portal>
    </DropdownMenu.Root>
  );
}

function UserMenu({ me }: { me: User }) {
  const qc = useQueryClient();
  const router = useRouter();
  const logout = async () => {
    await api("/auth/logout", { method: "POST" });
    qc.clear();
    router.replace("/login");
  };
  return (
    <div className="mt-4 flex items-center gap-3 rounded-lg border bg-card/60 p-2.5">
      <MemberAvatar user={me} size={34} />
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium">{me.display_name}</p>
        <p className="truncate text-xs text-muted-foreground">{me.is_demo ? "Demo visitor" : me.email}</p>
      </div>
      <Link href="/account" className="rounded-md p-1.5 text-muted-foreground hover:bg-accent hover:text-foreground" aria-label="Account settings">
        <UserCog className="size-4" />
      </Link>
      <button onClick={logout} className="rounded-md p-1.5 text-muted-foreground hover:bg-accent hover:text-foreground" aria-label="Sign out">
        <LogOut className="size-4" />
      </button>
    </div>
  );
}
