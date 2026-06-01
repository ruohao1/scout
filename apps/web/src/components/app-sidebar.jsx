import {
  BotIcon,
  BriefcaseBusinessIcon,
  CommandIcon,
  HistoryIcon,
  PlusIcon,
  Settings2Icon,
  TargetIcon,
} from "lucide-react"

import { NavUser } from "@/components/nav-user"
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarHeader,
  SidebarInput,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  useSidebar,
} from "@/components/ui/sidebar"

const navItems = [
  { id: "chat", title: "Chat", icon: <BotIcon /> },
  { id: "jobs", title: "Jobs", icon: <BriefcaseBusinessIcon /> },
  { id: "matches", title: "Matches", icon: <TargetIcon /> },
  { id: "settings", title: "Settings", icon: <Settings2Icon /> },
]

export function AppSidebar({ activeView, threads, activeThreadId, onViewChange, onThreadSelect, onNewThread, ...props }) {
  const { open, setOpen } = useSidebar()
  const showContextPanel = activeView === "chat" && open

  function selectView(view) {
    onViewChange(view)
  }

  return (
    <Sidebar collapsible="icon" className="overflow-hidden border-r border-sidebar-border/70 *:data-[sidebar=sidebar]:flex-row" {...props}>
      <Sidebar collapsible="none" className="scout-icon-rail w-[calc(var(--sidebar-width-icon)+1px)]! border-r border-sidebar-border/70 bg-sidebar/80">
        <SidebarHeader>
          <SidebarMenu>
            <SidebarMenuItem>
              <SidebarMenuButton size="lg" asChild className="scout-home-button md:h-8 md:p-0">
                <a
                  href="#"
                  aria-label="Scout home"
                  onClick={(event) => {
                    event.preventDefault()
                    selectView("chat")
                  }}
                >
                  <div className="flex aspect-square size-8 items-center justify-center rounded-lg bg-sidebar-primary text-sidebar-primary-foreground">
                    <CommandIcon className="size-4" />
                  </div>
                  <div className="grid flex-1 text-left text-sm leading-tight">
                    <span className="truncate font-medium">Scout</span>
                    <span className="truncate text-xs">Advisor</span>
                  </div>
                </a>
              </SidebarMenuButton>
            </SidebarMenuItem>
          </SidebarMenu>
        </SidebarHeader>
        <SidebarContent>
          <SidebarGroup>
            <SidebarGroupContent className="px-1.5 md:px-0">
              <SidebarMenu>
                {navItems.map((item) => (
                  <SidebarMenuItem key={item.id}>
                    <SidebarMenuButton
                      tooltip={{ children: item.title, hidden: false }}
                      onClick={() => selectView(item.id)}
                      isActive={activeView === item.id}
                      className="px-2.5 md:px-2"
                    >
                      {item.icon}
                      <span>{item.title}</span>
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                ))}
              </SidebarMenu>
            </SidebarGroupContent>
          </SidebarGroup>
        </SidebarContent>
        <SidebarFooter className="mt-auto">
          <NavUser onProfileClick={() => selectView("profiles")} isActive={activeView === "profiles"} />
        </SidebarFooter>
      </Sidebar>

      {showContextPanel && <Sidebar collapsible="none" className="hidden min-w-0 flex-1 bg-sidebar/70 md:flex">
        <SidebarHeader className="gap-3.5 border-b border-sidebar-border/70 p-4">
          <div className="flex w-full items-center justify-between gap-3">
            <div>
              <div className="text-base font-medium text-foreground">Chat</div>
              <p className="text-xs text-muted-foreground">Conversation history</p>
            </div>
            <button className="sidebar-action" type="button" onClick={onNewThread} aria-label="New chat">
              <PlusIcon className="size-4" />
            </button>
          </div>
          <SidebarInput placeholder="Search threads..." />
        </SidebarHeader>
        <SidebarContent>
          <SidebarGroup className="px-2 py-2">
            <SidebarGroupContent>
              {threads.map((row) => {
                const isActive = row.id === activeThreadId
                return (
                  <a
                    href="#"
                    key={row.id || row.title}
                    className="flex min-w-0 flex-col items-start gap-2 rounded-xl px-3 py-3 text-sm leading-tight transition-colors hover:bg-sidebar-accent hover:text-sidebar-accent-foreground data-[active=true]:bg-sidebar-accent data-[active=true]:text-sidebar-accent-foreground"
                    data-active={isActive}
                    onClick={(event) => {
                      event.preventDefault()
                      onThreadSelect(row.id)
                    }}
                  >
                    <div className="flex w-full min-w-0 items-center gap-2">
                      <HistoryIcon className="size-3.5 shrink-0 text-muted-foreground" />
                      <span className="min-w-0 flex-1 truncate font-medium">{row.title}</span>
                      <span className="shrink-0 text-xs text-muted-foreground">{row.time}</span>
                    </div>
                    <span className="line-clamp-2 w-full min-w-0 text-xs leading-5 text-muted-foreground">{row.detail}</span>
                  </a>
                )
              })}
            </SidebarGroupContent>
          </SidebarGroup>
        </SidebarContent>
      </Sidebar>}
    </Sidebar>
  )
}
