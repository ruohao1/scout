import { SidebarMenu, SidebarMenuButton, SidebarMenuItem } from "@/components/ui/sidebar"
import { UserRoundIcon } from "lucide-react"

export function NavUser({ onProfileClick, isActive = false }) {
  return (
    <SidebarMenu>
      <SidebarMenuItem>
        <SidebarMenuButton
          size="lg"
          className="scout-profile-button md:h-8 md:p-0"
          onClick={onProfileClick}
          isActive={isActive}
          tooltip={{ children: "Profiles", hidden: false }}
        >
          <UserRoundIcon />
          <span>Profiles</span>
        </SidebarMenuButton>
      </SidebarMenuItem>
    </SidebarMenu>
  )
}
