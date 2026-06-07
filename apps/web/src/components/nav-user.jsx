import { SidebarMenu, SidebarMenuButton, SidebarMenuItem } from "@/components/ui/sidebar"
import { UserRoundIcon } from "lucide-react"
import { NavLink } from "react-router-dom"

export function NavUser({ onProfileClick, isActive = false }) {
  return (
    <SidebarMenu>
      <SidebarMenuItem>
        <SidebarMenuButton
          size="lg"
          asChild
          className="scout-profile-button md:h-8 md:p-0"
          isActive={isActive}
          tooltip={{ children: "Profiles", hidden: false }}
        >
          <NavLink to="/profiles" onClick={onProfileClick}>
            <UserRoundIcon />
            <span>Profiles</span>
          </NavLink>
        </SidebarMenuButton>
      </SidebarMenuItem>
    </SidebarMenu>
  )
}
