import { Avatar } from "flowbite-react";
import { useState } from "react";

const DEFAULT_AVATAR = "/user-avatar.svg";

interface UserAvatarProps {
  fullName?: string | null;
  email?: string | null;
  imageUrl?: string | null;
  showName?: boolean;
  size?: "xs" | "sm" | "md" | "lg" | "xl";
}

function buildAvatarUrl(
  imageUrl?: string | null,
  email?: string | null,
  fullName?: string | null,
): string {
  if (imageUrl?.trim()) {
    return imageUrl.trim();
  }

  const seed = encodeURIComponent(email ?? fullName ?? "admin");
  return `https://api.dicebear.com/7.x/avataaars/png?seed=${seed}&size=40`;
}

export function UserAvatar({
  fullName,
  email,
  imageUrl,
  showName = true,
  size = "sm",
}: UserAvatarProps) {
  const displayName = fullName?.trim() || email || "User";
  const [avatarSrc, setAvatarSrc] = useState(() =>
    buildAvatarUrl(imageUrl, email, fullName),
  );

  return (
    <div className="flex items-center gap-3">
      <Avatar
        alt={displayName}
        className="overflow-hidden rounded-full  bg-slate-100"
        theme={{
          root: {
            inner: "relative overflow-hidden rounded-full",
            img: { on: "rounded-full object-cover" },
          },
        }}
        img={(imageProps) => (
          <img
            {...imageProps}
            className={`${imageProps.className ?? ""} h-[40px] w-[40px] rounded-full object-cover bg-slate-100`}
            src={avatarSrc}
            onError={() => setAvatarSrc(DEFAULT_AVATAR)}
          />
        )}
        rounded
        size={size}
      />
      {showName ? (
        <span className="text-sm font-medium text-gray-700">{displayName}</span>
      ) : null}
    </div>
  );
}
