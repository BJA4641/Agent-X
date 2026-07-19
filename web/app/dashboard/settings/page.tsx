import { supabaseServer } from "@/lib/supabase/server";
import ChannelConnections from "@/components/ChannelConnections";

export default async function SettingsPage() {
  const sb = supabaseServer();
  const { data: { user } } = await sb.auth.getUser();
  if (!user) return null;

  return (
    <div>
      <h1>Channel settings</h1>
      <p className="note" style={{ maxWidth: 640 }}>
        Connect your social accounts so Agent-X can publish your approved content.
        Tokens are encrypted at rest and only read server-side when publishing.
        AI engine settings live in the admin <b>Developer console</b> (admins only).
      </p>

      <h2 style={{ marginTop: 28 }}>Channel connections</h2>
      <p className="note" style={{ maxWidth: 720, marginBottom: 12 }}>
        Connect each account you want Agent-X to post to. Instagram auto-posting works once
        your Meta app is approved; until then Studio prepares everything and one click copies
        the caption/video for manual upload.
      </p>
      <ChannelConnections />
    </div>
  );
}
