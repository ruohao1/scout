import { useState } from "react"
import { NavLink } from "react-router-dom"
import {
  BotIcon,
  BriefcaseBusinessIcon,
  CommandIcon,
  CopyIcon,
  EllipsisIcon,
  HistoryIcon,
  PencilIcon,
  PlusIcon,
  RefreshCwIcon,
  Settings2Icon,
  TargetIcon,
  Trash2Icon,
  UserRoundIcon,
} from "lucide-react"

import { NavUser } from "@/components/nav-user"
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog"
import {
  ContextMenu,
  ContextMenuContent,
  ContextMenuItem,
  ContextMenuSeparator,
  ContextMenuTrigger,
} from "@/components/ui/context-menu"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
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
import { profileName } from "../lib/profile.js"

const navItems = [
  { id: "chat", title: "Chat", path: "/chat", icon: <BotIcon /> },
  { id: "jobs", title: "Jobs", path: "/jobs", icon: <BriefcaseBusinessIcon /> },
  { id: "candidate", title: "Candidate", path: "/candidate", icon: <UserRoundIcon /> },
  { id: "targetProfiles", title: "Target Profiles", path: "/target-profiles", icon: <TargetIcon /> },
  { id: "matches", title: "Matches", path: "/matches", icon: <TargetIcon /> },
  { id: "settings", title: "Settings", path: "/settings", icon: <Settings2Icon /> },
]

export function AppSidebar({
  activeView,
  threads,
  activeThreadId,
  jobs,
  selectedJobId,
  isLoadingJobs,
  profiles,
  selectedProfileId,
  isLoadingProfiles,
  onViewChange,
  onThreadSelect,
  onNewThread,
  onThreadRename,
  onThreadDuplicate,
  onThreadDelete,
  onJobsRefresh,
  onProfileSelect,
  onProfilesRefresh,
  ...props
}) {
  const { open } = useSidebar()
  const [renamingThreadId, setRenamingThreadId] = useState(null)
  const [renameDraft, setRenameDraft] = useState("")
  const [deleteTarget, setDeleteTarget] = useState(null)
  const showContextPanel = (activeView === "chat" || (activeView === "jobs" && selectedJobId) || activeView === "targetProfiles" || activeView === "matches") && open

  function startRename(thread) {
    setRenamingThreadId(thread.id)
    setRenameDraft(thread.title)
  }

  function commitRename(thread) {
    const nextTitle = renameDraft.trim()
    setRenamingThreadId(null)
    setRenameDraft("")
    if (nextTitle && nextTitle !== thread.title) {
      onThreadRename(thread.id, nextTitle)
    }
  }

  function cancelRename() {
    setRenamingThreadId(null)
    setRenameDraft("")
  }

  function selectThreadFromKeyboard(event, threadId) {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault()
      onThreadSelect(threadId)
    }
  }

  return (
    <Sidebar collapsible="icon" className="overflow-hidden border-r border-sidebar-border/70 *:data-[sidebar=sidebar]:flex-row" {...props}>
      <Sidebar collapsible="none" className="scout-icon-rail w-[calc(var(--sidebar-width-icon)+1px)]! border-r border-sidebar-border/70 bg-sidebar/80">
        <SidebarHeader>
          <SidebarMenu>
            <SidebarMenuItem>
              <SidebarMenuButton size="lg" asChild className="scout-home-button md:h-8 md:p-0">
                <NavLink to="/chat" aria-label="Scout home" onClick={() => onViewChange("chat")}>
                  <div className="flex aspect-square size-8 items-center justify-center rounded-lg bg-sidebar-primary text-sidebar-primary-foreground">
                    <CommandIcon className="size-4" />
                  </div>
                  <div className="grid flex-1 text-left text-sm leading-tight">
                    <span className="truncate font-medium">Scout</span>
                    <span className="truncate text-xs">Advisor</span>
                  </div>
                </NavLink>
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
                      asChild
                      isActive={activeView === item.id}
                      className="px-2.5 md:px-2"
                    >
                      <NavLink to={item.path} onClick={() => onViewChange(item.id)}>
                        {item.icon}
                        <span>{item.title}</span>
                      </NavLink>
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                ))}
              </SidebarMenu>
            </SidebarGroupContent>
          </SidebarGroup>
        </SidebarContent>
        <SidebarFooter className="mt-auto">
          <NavUser onProfileClick={() => onViewChange("candidate")} isActive={activeView === "candidate"} />
        </SidebarFooter>
      </Sidebar>

      {showContextPanel && <Sidebar collapsible="none" className="hidden min-w-0 flex-1 bg-sidebar/70 md:flex">
        {activeView === "chat" ? (
          <ChatHistoryPanel
            threads={threads}
            activeThreadId={activeThreadId}
            renamingThreadId={renamingThreadId}
            renameDraft={renameDraft}
            setRenameDraft={setRenameDraft}
            onNewThread={onNewThread}
            onThreadSelect={onThreadSelect}
            onThreadRenameCommit={commitRename}
            onThreadRenameCancel={cancelRename}
            onThreadKeyboardSelect={selectThreadFromKeyboard}
            onThreadRenameStart={startRename}
            onThreadDuplicate={onThreadDuplicate}
            onThreadDelete={(thread) => setDeleteTarget(thread)}
          />
        ) : activeView === "jobs" ? (
          <JobsPanel
            jobs={jobs || []}
            selectedJobId={selectedJobId}
            isLoading={isLoadingJobs}
            onRefresh={onJobsRefresh}
          />
        ) : (
          <ProfilesPanel
            profiles={profiles || []}
            selectedProfileId={selectedProfileId}
            isLoading={isLoadingProfiles}
            onRefresh={onProfilesRefresh}
            onSelectProfile={onProfileSelect}
          />
        )}
      </Sidebar>}
      <AlertDialog open={Boolean(deleteTarget)} onOpenChange={(open) => !open && setDeleteTarget(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete conversation?</AlertDialogTitle>
            <AlertDialogDescription>
              This removes "{deleteTarget?.title || "this conversation"}" from this browser. If it is the last conversation, Scout will create a fresh empty one.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              className="bg-destructive/10 text-destructive hover:bg-destructive/20 focus-visible:border-destructive/40 focus-visible:ring-destructive/20"
              onClick={() => {
                if (deleteTarget) onThreadDelete(deleteTarget.id)
                setDeleteTarget(null)
              }}
            >
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </Sidebar>
  )
}

function JobsPanel({ jobs, selectedJobId, isLoading, onRefresh }) {
  return (
    <>
      <SidebarHeader className="gap-3.5 border-b border-sidebar-border/70 p-4">
        <div className="flex w-full items-center justify-between gap-3">
          <div>
            <div className="text-base font-medium text-foreground">Jobs</div>
            <p className="text-xs text-muted-foreground">Selected posting</p>
          </div>
          <button className="sidebar-action" type="button" onClick={onRefresh} disabled={isLoading} aria-label="Refresh jobs">
            <RefreshCwIcon className={isLoading ? "size-4 animate-spin" : "size-4"} />
          </button>
        </div>
        <div className="flex items-center justify-between text-xs text-muted-foreground">
          <span>{isLoading ? "Refreshing..." : "Imported postings"}</span>
          <span>{jobs.length}</span>
        </div>
      </SidebarHeader>
      <SidebarContent>
        <SidebarGroup className="px-2 py-2">
          <SidebarGroupContent>
            {!isLoading && jobs.length === 0 && (
              <div className="px-3 py-3 text-sm text-muted-foreground">
                No jobs loaded yet. Open Jobs to refresh imported postings.
              </div>
            )}
            {jobs.map((job) => {
              const isActive = job.id === selectedJobId
              const subtitle = [job.company, job.location].filter(Boolean).join(' / ') || 'Unspecified'
              const detail = job.salary || job.contract_type
              return (
                <NavLink
                  key={job.id}
                  to={`/jobs/${job.id}`}
                  state={{ job }}
                  className="flex w-full min-w-0 items-start gap-2 rounded-xl px-3 py-3 text-left text-sm leading-tight transition-colors hover:bg-sidebar-accent hover:text-sidebar-accent-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sidebar-ring data-[active=true]:bg-sidebar-accent data-[active=true]:text-sidebar-accent-foreground"
                  data-active={isActive}
                >
                  <BriefcaseBusinessIcon className="mt-0.5 size-3.5 shrink-0 text-muted-foreground" />
                  <span className="flex min-w-0 flex-1 flex-col gap-2">
                    <span className="min-w-0 truncate font-medium">{job.title}</span>
                    <span className="line-clamp-2 min-w-0 text-xs leading-5 text-muted-foreground">{subtitle}</span>
                    {detail && <span className="min-w-0 truncate text-xs font-medium text-muted-foreground">{detail}</span>}
                  </span>
                </NavLink>
              )
            })}
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>
    </>
  )
}

function ChatHistoryPanel({
  threads,
  activeThreadId,
  renamingThreadId,
  renameDraft,
  setRenameDraft,
  onNewThread,
  onThreadSelect,
  onThreadRenameCommit,
  onThreadRenameCancel,
  onThreadKeyboardSelect,
  onThreadRenameStart,
  onThreadDuplicate,
  onThreadDelete,
}) {
  return (
    <>
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
              const isRenaming = row.id === renamingThreadId
              return (
                <ContextMenu key={row.id || row.title}>
                  <ContextMenuTrigger asChild>
                    <div
                      role="button"
                      tabIndex={0}
                      className="group/thread flex min-w-0 items-start gap-2 rounded-xl px-3 py-3 text-left text-sm leading-tight transition-colors hover:bg-sidebar-accent hover:text-sidebar-accent-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sidebar-ring data-[active=true]:bg-sidebar-accent data-[active=true]:text-sidebar-accent-foreground"
                      data-active={isActive}
                      onClick={() => {
                        if (!isRenaming) onThreadSelect(row.id)
                      }}
                      onKeyDown={(event) => {
                        if (!isRenaming) onThreadKeyboardSelect(event, row.id)
                      }}
                    >
                      <div className="flex min-w-0 flex-1 flex-col items-start gap-2">
                        <div className="flex w-full min-w-0 items-center gap-2">
                          <HistoryIcon className="size-3.5 shrink-0 text-muted-foreground" />
                          {isRenaming ? (
                            <input
                              autoFocus
                              className="min-w-0 flex-1 rounded-md border border-sidebar-border bg-background px-2 py-1 text-sm font-medium text-foreground outline-none ring-sidebar-ring focus:ring-2"
                              value={renameDraft}
                              onChange={(event) => setRenameDraft(event.target.value)}
                              onClick={(event) => event.stopPropagation()}
                              onBlur={() => onThreadRenameCommit(row)}
                              onKeyDown={(event) => {
                                if (event.key === "Enter") {
                                  event.preventDefault()
                                  onThreadRenameCommit(row)
                                }
                                if (event.key === "Escape") {
                                  event.preventDefault()
                                  onThreadRenameCancel()
                                }
                              }}
                            />
                          ) : (
                            <span className="min-w-0 flex-1 truncate font-medium">{row.title}</span>
                          )}
                          <span className="shrink-0 text-xs text-muted-foreground">{row.time}</span>
                        </div>
                        <span className="line-clamp-2 w-full min-w-0 text-xs leading-5 text-muted-foreground">{row.detail}</span>
                      </div>
                      <ThreadActionsDropdown
                        thread={row}
                        onRename={() => onThreadRenameStart(row)}
                        onDuplicate={() => onThreadDuplicate(row.id)}
                        onDelete={() => onThreadDelete(row)}
                      />
                    </div>
                  </ContextMenuTrigger>
                  <ContextMenuContent className="w-40">
                    <ThreadActionItems
                      onRename={() => onThreadRenameStart(row)}
                      onDuplicate={() => onThreadDuplicate(row.id)}
                      onDelete={() => onThreadDelete(row)}
                      menuType="context"
                    />
                  </ContextMenuContent>
                </ContextMenu>
              )
            })}
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>
    </>
  )
}

function ProfilesPanel({ profiles, selectedProfileId, isLoading, onRefresh, onSelectProfile }) {
  return (
    <>
      <SidebarHeader className="gap-3.5 border-b border-sidebar-border/70 p-4">
        <div className="flex w-full items-center justify-between gap-3">
          <div>
            <div className="text-base font-medium text-foreground">Target profiles</div>
            <p className="text-xs text-muted-foreground">Matching personas</p>
          </div>
          <button className="sidebar-action" type="button" onClick={onRefresh} disabled={isLoading} aria-label="Refresh target profiles">
            <RefreshCwIcon className={isLoading ? "size-4 animate-spin" : "size-4"} />
          </button>
        </div>
        <div className="flex items-center justify-between text-xs text-muted-foreground">
          <span>{isLoading ? "Refreshing..." : "Saved target profiles"}</span>
          <span>{profiles.length}</span>
        </div>
      </SidebarHeader>
      <SidebarContent>
        <SidebarGroup className="px-2 py-2">
          <SidebarGroupContent>
            {!isLoading && profiles.length === 0 && (
              <div className="px-3 py-3 text-sm text-muted-foreground">
                No target profiles yet. Open Target Profiles to create one.
              </div>
            )}
            {profiles.map((profile) => {
              const isActive = profile.id === selectedProfileId
              const title = profileName(profile)
              const subtitle = profileSubtitle(profile, title)
              return (
                <button
                  type="button"
                  key={profile.id}
                  className="flex w-full min-w-0 items-start gap-2 rounded-xl px-3 py-3 text-left text-sm leading-tight transition-colors hover:bg-sidebar-accent hover:text-sidebar-accent-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sidebar-ring data-[active=true]:bg-sidebar-accent data-[active=true]:text-sidebar-accent-foreground"
                  data-active={isActive}
                  onClick={() => onSelectProfile(profile.id)}
                >
                  <UserRoundIcon className="mt-0.5 size-3.5 shrink-0 text-muted-foreground" />
                  <span className="flex min-w-0 flex-1 flex-col gap-2">
                    <span className="min-w-0 truncate font-medium">{title}</span>
                    <span className="line-clamp-2 min-w-0 text-xs leading-5 text-muted-foreground">
                      {subtitle}
                    </span>
                  </span>
                </button>
              )
            })}
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>
    </>
  )
}

function profileSubtitle(profile, title) {
  const roles = profile.target_roles || []
  const subtitleRoles = roles[0] === title ? roles.slice(1) : roles
  return subtitleRoles.join(', ') || profile.seniority || 'General target'
}

function ThreadActionsDropdown({ thread, onRename, onDuplicate, onDelete }) {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button
          type="button"
          className="mt-[-0.25rem] flex size-7 shrink-0 items-center justify-center rounded-lg text-muted-foreground opacity-0 transition-opacity hover:bg-sidebar-accent-foreground/10 hover:text-foreground focus-visible:opacity-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sidebar-ring group-hover/thread:opacity-100 data-open:opacity-100"
          aria-label={`Open actions for ${thread.title}`}
          onClick={(event) => event.stopPropagation()}
        >
          <EllipsisIcon className="size-4" />
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-40">
        <ThreadActionItems onRename={onRename} onDuplicate={onDuplicate} onDelete={onDelete} menuType="dropdown" />
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

function ThreadActionItems({ onRename, onDuplicate, onDelete, menuType }) {
  const Item = menuType === "context" ? ContextMenuItem : DropdownMenuItem
  const Separator = menuType === "context" ? ContextMenuSeparator : DropdownMenuSeparator

  return (
    <>
      <Item onSelect={onRename}>
        <PencilIcon />
        Rename
      </Item>
      <Item onSelect={onDuplicate}>
        <CopyIcon />
        Duplicate
      </Item>
      <Separator />
      <Item variant="destructive" onSelect={onDelete}>
        <Trash2Icon />
        Delete
      </Item>
    </>
  )
}
