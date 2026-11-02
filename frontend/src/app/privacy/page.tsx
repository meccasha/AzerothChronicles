import Link from "next/link";

export const metadata = { title: "Privacy" };

export default function PrivacyPage() {
  return (
    <main className="mx-auto max-w-3xl px-6 py-12 text-sm leading-relaxed text-foreground/90">
      <Link href="/" className="text-gold hover:underline">
        ← Back
      </Link>
      <h1 className="mt-6 text-3xl font-bold gold-text">Privacy policy (template)</h1>
      <p className="mt-2 text-xs text-muted-foreground">Operators: adapt this template to your deployment and jurisdiction before going live.</p>
      <h2 className="mt-8 text-lg">What we store</h2>
      <ul className="mt-2 list-disc space-y-1 pl-5">
        <li>Account: email, display name, and a salted Argon2 password hash.</li>
        <li>Characters you link or declare, and game events reported by your addon uploads or Battle.net syncs.</li>
        <li>Content you create: manual events, comments, reactions, screenshots (re-encoded to strip metadata).</li>
        <li>Battle.net OAuth tokens, encrypted at rest. We never request or store your Battle.net password.</li>
      </ul>
      <h2 className="mt-6 text-lg">Who can see it</h2>
      <p className="mt-2">Group content is visible only to members of that group. Groups are never public. Characters you link are visible to members of groups you belong to.</p>
      <h2 className="mt-6 text-lg">Your controls</h2>
      <ul className="mt-2 list-disc space-y-1 pl-5">
        <li>Export all of your data as JSON from Account → Your data.</li>
        <li>Delete your account at any time; your personal data is removed. Shared group events you took part in remain, without your profile.</li>
        <li>Unlink Battle.net to delete stored tokens; revoke companion tokens at any time.</li>
      </ul>
      <h2 className="mt-6 text-lg">Third parties</h2>
      <p className="mt-2">When Battle.net is linked, we call Blizzard&apos;s official APIs on your behalf. Azeroth Chronicles is not affiliated with or endorsed by Blizzard Entertainment.</p>
      <h2 className="mt-6 text-lg">Contact</h2>
      <p className="mt-2">[Operator name and contact address]</p>
    </main>
  );
}
