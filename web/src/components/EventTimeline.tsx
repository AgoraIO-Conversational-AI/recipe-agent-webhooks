"use client";

export type TimelineEvent = {
	id: string;
	ts: number;
	kind: "state" | "metric" | "error" | "turn";
	label: string;
	detail?: string;
};

type EventTimelineProps = {
	events: TimelineEvent[];
};

const KIND_STYLES: Record<TimelineEvent["kind"], { badge: string; dot: string }> = {
	state: {
		badge: "bg-blue-500/10 text-blue-400 border border-blue-500/20",
		dot: "bg-blue-400",
	},
	metric: {
		badge: "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20",
		dot: "bg-emerald-400",
	},
	error: {
		badge: "bg-red-500/10 text-red-400 border border-red-500/20",
		dot: "bg-red-400",
	},
	turn: {
		badge: "bg-violet-500/10 text-violet-400 border border-violet-500/20",
		dot: "bg-violet-400",
	},
};

function formatEventTime(ts: number): string {
	return new Intl.DateTimeFormat(undefined, {
		hour: "2-digit",
		minute: "2-digit",
		second: "2-digit",
		hour12: false,
	}).format(new Date(ts));
}

export function EventTimeline({ events }: EventTimelineProps) {
	const displayed = [...events].reverse();

	return (
		<section
			className="flex h-full min-h-0 w-full flex-col overflow-hidden rounded-2xl border border-border bg-card/20"
			aria-label="Event timeline"
		>
			<div className="flex h-14 shrink-0 items-center justify-between border-b border-border px-4">
				<div>
					<h2 className="text-sm font-semibold text-foreground">Event Timeline</h2>
					<p className="text-xs text-muted-foreground">
						Live agent events — state, metrics, errors, turns
					</p>
				</div>
				<span className="rounded-full border border-border bg-card/60 px-2 py-0.5 text-xs text-muted-foreground">
					{events.length} / 50
				</span>
			</div>

			<div className="flex min-h-0 flex-1 flex-col gap-1 overflow-y-auto px-3 py-3">
				{displayed.length === 0 ? (
					<div className="flex h-full items-center justify-center text-center text-sm text-muted-foreground">
						Start a conversation to see events here.
					</div>
				) : (
					displayed.map((event) => {
						const styles = KIND_STYLES[event.kind];
						return (
							<div
								key={event.id}
								className="flex items-start gap-2 rounded-lg border border-border/40 bg-card/30 px-3 py-2 text-xs"
							>
								<div className="mt-1.5 flex-shrink-0">
									<span className={`block h-1.5 w-1.5 rounded-full ${styles.dot}`} />
								</div>
								<div className="min-w-0 flex-1">
									<div className="flex flex-wrap items-center gap-1.5">
										<span
											className={`rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${styles.badge}`}
										>
											{event.kind}
										</span>
										<span className="font-medium text-foreground">{event.label}</span>
										{event.detail ? (
											<span className="truncate text-muted-foreground">
												{event.detail}
											</span>
										) : null}
									</div>
								</div>
								<span className="flex-shrink-0 font-mono text-[10px] text-muted-foreground/60">
									{formatEventTime(event.ts)}
								</span>
							</div>
						);
					})
				)}
			</div>
		</section>
	);
}
