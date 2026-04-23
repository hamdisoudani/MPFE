"use client";
import { useEffect, useState } from "react";
import "@blocknote/core/fonts/inter.css";
import "@blocknote/mantine/style.css";
import { BlockNoteView } from "@blocknote/mantine";
import { useCreateBlockNote } from "@blocknote/react";

export function LessonBlockNoteView({ markdown }: { markdown: string }) {
  const editor = useCreateBlockNote();
  const [ready, setReady] = useState(false);
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const blocks = await editor.tryParseMarkdownToBlocks(markdown || "");
        if (!cancelled) editor.replaceBlocks(editor.document, blocks);
      } finally { if (!cancelled) setReady(true); }
    })();
    return () => { cancelled = true; };
  }, [markdown, editor]);
  return (
    <div className="blocknote-shell -mx-1">
      <BlockNoteView editor={editor} editable={false} theme="light" />
      {!ready && <div className="py-2 text-xs text-fg-muted">Rendering…</div>}
    </div>
  );
}
