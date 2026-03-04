/**
 * Presence indicator showing connected collaborator avatars.
 */

import type { Collaborator } from "./hooks/useCollaboration";

interface CollaboratorAvatarsProps {
  collaborators: Collaborator[];
  myUserId: string;
}

export function CollaboratorAvatars({
  collaborators,
  myUserId,
}: CollaboratorAvatarsProps) {
  const others = collaborators.filter((c) => c.user_id !== myUserId);
  if (others.length === 0) return null;

  return (
    <div className="flex items-center gap-1">
      {others.map((c) => (
        <div
          key={c.user_id}
          className="w-6 h-6 rounded-full flex items-center justify-center text-[10px] font-bold text-white"
          style={{ backgroundColor: c.color }}
          title={c.display_name}
        >
          {c.display_name.charAt(0).toUpperCase()}
        </div>
      ))}
      <span className="text-[10px] text-[hsl(var(--muted-foreground))] ml-1">
        {others.length} collaborator{others.length !== 1 ? "s" : ""}
      </span>
    </div>
  );
}
