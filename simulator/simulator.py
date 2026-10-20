"""SecondSight synthetic match simulator.

Generates a seeded, football-realistic synthetic event stream:
passes, shots, tackles, possession changes, pressure events, match metadata.

Events carry pitch coordinates and a match clock, so downstream agents can
derive geometry (pass distance, field tilt, pressure maps) rather than
working with flat counts.
"""

from __future__ import annotations

import json
import math
import random
import time
from dataclasses import asdict, dataclass, field
from typing import Iterator, Optional

# ---------------------------------------------------------------- constants

PITCH = {"length": 105.0, "width": 68.0}  # metres, FIFA standard

EVENT_TYPES = {
    "PASS",
    "SHOT",
    "SAVE",
    "GOAL",
    "TACKLE",
    "FOUL",
    "INTERCEPTION",
    "POSSESSION_CHANGE",
    "PRESSURE",
    "CORNER",
    "CARD_YELLOW",
    "CARD_RED",
    "SUBSTITUTION",
    "MATCH_START",
    "HALF_START",
    "HALF_END",
    "MATCH_END",
}

RESULTS = {"ATTEMPT_OFF_TARGET", "ATTEMPT_SAVED", "ATTEMPT_BLOCKED", "ATTEMPT_GOAL"}


# ---------------------------------------------------------------- schema


@dataclass
class Player:
    name: str
    role: str  # GK DEF MID FWD
    skill: float  # 0..1
    speed: float  # 0..1


@dataclass
class Team:
    id: str
    name: str
    color: str
    players: list[Player]


@dataclass
class Event:
    """One football event. Timestamp is in simulated seconds (not wall clock)."""

    t: float  # match clock in seconds
    event_type: str
    team: Optional[str] = None
    player: Optional[str] = None
    x: Optional[float] = None
    y: Optional[float] = None
    to_x: Optional[float] = None
    to_y: Optional[float] = None
    outcome: Optional[str] = None
    extra: dict = field(default_factory=dict)

    def to_json(self) -> str:
        d = asdict(self)
        d.pop("event_type")
        return json.dumps({"type": self.event_type, **d})



# ---------------------------------------------------------------- squads

# Synthetic squads (fictional clubs & players — 100% synthetic data, no real names)
FIRST_NAMES = [
    "Marcus", "Diego", "Kenta", "Emeka", "Luca", "Tomas", "Ivan", "Pedro", "Karim",
    "Oliver", "Mateo", "Jamal", "Theo", "Nikola", "Andres", "Felix", "Sameh", "Yuto",
]
LAST_NAMES = [
    "Varela", "Okafor", "Tanaka", "Silva", "Novak", "Berg", "Costa", "Haddad", "Morel",
    "Whitfield", "Rossi", "Baptiste", "Fournier", "Petrov", "Mbeki", "Sharma", "Duarte",
]

ROLES = (
    ["GK"]
    + ["DEF"] * 4
    + ["MID"] * 4
    + ["FWD"] * 3
)


def make_team(team_id: str, name: str, color: str, rng: random.Random) -> Team:
    players = [
        Player(
            name=f"{rng.choice(FIRST_NAMES)} {rng.choice(LAST_NAMES)}",
            role=role,
            skill=max(0.3, min(0.95, rng.random() * 0.65 + 0.2)),
            speed=max(0.3, min(0.95, rng.random() * 0.65 + 0.2)),
        )
        for role in ROLES
    ]
    return Team(id=team_id, name=name, color=color, players=players)


def default_teams(seed: int) -> tuple[Team, Team]:
    rng = random.Random(seed * 7919 + 13)
    home = make_team("HOME", "Northgate FC", "#1f6feb", rng)
    away = make_team("AWAY", "Rivermouth Athletic", "#d29922", rng)
    return home, away


# ---------------------------------------------------------------- engine


class MatchSimulator:
    """Seeded simulator producing a stream of football-realistic events.

    - Match clock advances at `speed` x real time.
    - Possession changes produce PRESSURE events and drive momentum-style runs.
    - Events carry coordinates; pass results depend on distance & player skill.
    """

    def __init__(self, seed: int = 42, speed: float = 10.0, teams: tuple[Team, Team] | None = None):
        self.seed = seed
        self.rng = random.Random(seed)
        self.speed = speed  # simulated seconds per wall-clock second
        self.teams = teams if teams else default_teams(seed)
        self.clock = 0.0
        self.score = {"HOME": 0, "AWAY": 0}
        self.cards = []
        self.subs = []
        self.possession: str = self.rng.choice(["HOME", "AWAY"])
        self.possessing_player: Optional[Player] = None
        self.ball: tuple[float, float] = (52.5, 34.0)
        self._half = 1
        self._pressure_counter = 0


    # ---------- helpers

    def _team(self, team_id: str) -> Team:
        return self.teams[0] if team_id == "HOME" else self.teams[1]

    def _pick_player(self, team_id: str, weighted_role: str | None = None) -> Player:
        players = self._team(team_id).players
        if weighted_role:
            weighted = [p for p in players if p.role == weighted_role]
            if weighted:
                return self.rng.choice(weighted)
        return self.rng.choice(players)

    def _attack_dir(self, team_id: str) -> float:
        # HOME attacks +x in first half, flips at half time (simplified)
        if team_id == "HOME":
            return 1.0 if self._half == 1 else -1.0
        return -1.0 if self._half == 1 else 1.0

    # ---------- core transitions

    def _do_pass(self) -> Event:
        team = self.possession
        p = self.possessing_player or self._pick_player(team)
        direction = self._attack_dir(team)
        # Forward bias when scored against goalwards; short when under pressure
        under_pressure = self._pressure_counter > 0
        distance = self.rng.uniform(5, 45) * (0.6 if under_pressure else 1.0)
        # Mostly forward but allow genuinely sideways/backward play so possession
        # doesn't monotonically march toward the attacked goal
        angle = self.rng.uniform(-math.pi / 2.2, math.pi / 2.2)
        if self.rng.random() < 0.12:
            angle += math.pi  # backwards/switch pass



        to_x = min(max(self.ball[0] + direction * distance * math.cos(angle), 0), PITCH["length"])
        to_y = min(max(self.ball[1] + distance * math.sin(angle), 0), PITCH["width"])
        # In the attacking third, pull pass targets toward the goal's central
        # corridor (crosses/clipped passes into the box) so the ball doesn't get
        # pinned in goal-line corners
        proximity = max(0.0, 1.0 - abs(PITCH["length"] / 2.0 + direction * PITCH["length"] / 2.0 - to_x) / (PITCH["length"] / 2.0))
        zone_center_y = PITCH["width"] / 2
        to_y = to_y * (1 - 0.35 * proximity) + zone_center_y * 0.35 * proximity
        to_y = min(max(to_y, 0), PITCH["width"])
        pass_len = math.hypot(to_x - self.ball[0], to_y - self.ball[1])


        difficulty = min(1.0, pass_len / 50.0)
        success_prob = 0.93 - 0.55 * difficulty + 0.18 * (p.skill - 0.5) - (0.12 if under_pressure else 0)
        success = self.rng.random() < max(0.05, success_prob)

        ev = Event(
            t=self.clock,
            event_type="PASS",
            team=team,
            player=p.name,
            x=self.ball[0],
            y=self.ball[1],
            to_x=to_x if success else self.ball[0],
            to_y=to_y if success else self.ball[1],
            outcome="COMPLETE" if success else "INCOMPLETE",
            extra={"pass_length": round(pass_len, 2), "pass_difficulty": round(difficulty, 2)},
        )
        if success:
            self.ball = (to_x, to_y)
            self.possessing_player = self._team(team).players[
                self.rng.randrange(len(self._team(team).players))
            ]
        else:
            self._lose_possession()
        return ev

    def _lose_possession(self) -> None:
        self.possession = "AWAY" if self.possession == "HOME" else "HOME"
        self.possessing_player = self._pick_player(self.possession)
        self._pressure_counter = min(6, self._pressure_counter + 2)

    def _maybe_shot(self) -> Optional[Event]:
        team = self.possession
        bx, by = self.ball
        goal_x, goal_y = (PITCH["length"], PITCH["width"] / 2) if self._attack_dir(team) > 0 else (0, PITCH["width"] / 2)
        dist_goal = math.hypot(bx - goal_x, by - goal_y)
        # Shot likelihood rises super-linearly as the ball approaches goal, so
        # attempts cluster in dangerous areas instead of from distance
        if dist_goal > 40 or self.rng.random() > (0.05 + 0.85 * (1.0 - min(dist_goal, 40.0) / 40.0) ** 2.5):
            return None





        shooter = self._pick_player(team, "FWD") if self.rng.random() < 0.7 else self._pick_player(team)
        xg = max(0.01, math.exp(-dist_goal / 6.0) * 0.68)  # crude but plausible xG curve



        scored = self.rng.random() < xg
        off_m = self.rng.uniform(0, (0.15 if scored else 1.8) * max(1.0, dist_goal / 12))

        if scored:
            self.score[team] += 1
            outcome, ev_type = "ATTEMPT_GOAL", "GOAL"
        else:
            outcome = self.rng.choice(["ATTEMPT_OFF_TARGET", "ATTEMPT_SAVED", "ATTEMPT_BLOCKED"])
            ev_type = "SHOT"
        shot_speed = self.rng.uniform(70, 130)  # km/h plausible
        ev = Event(
            t=self.clock,
            event_type=ev_type,
            team=team,
            player=shooter.name,
            x=bx,
            y=by,
            to_x=goal_x,
            to_y=goal_y,
            outcome=outcome,
            extra={"xg": round(xg, 3), "shot_speed_kmh": round(shot_speed, 1), "distance_to_goal": round(dist_goal, 1)},
        )
        # after a shot, ball restarts (goal kick / save scenario)
        self._lose_possession()
        self.ball = (PITCH["length"] / 2 if not scored else self.ball[0], PITCH["width"] / 2)
        self._pressure_counter = 0
        return ev

    def _pressure_event(self) -> Optional[Event]:
        # Sustained pressure: opponents press high near losing-side's box.
        # Convention: `team` = the side doing the pressing, `player` = presser.
        if self._pressure_counter > 0 and self.rng.random() < 0.25:
            pressing = "AWAY" if self.possession == "HOME" else "HOME"
            bx, by = self.ball
            ev = Event(
                t=self.clock,
                event_type="PRESSURE",
                team=pressing,
                player=self._pick_player(pressing).name,
                x=bx,
                y=by,
                extra={"intensity": round(min(1.0, 0.17 * self._pressure_counter), 2)},
            )
            return ev
        return None


    def _tackle_event(self) -> Optional[Event]:
        if self.rng.random() < 0.06:
            team = self.possession
            opp = "AWAY" if team == "HOME" else "HOME"
            tackler = self._pick_player(opp, "DEF" if self.rng.random() < 0.55 else "MID")
            fouled = self.possessing_player or self._pick_player(team)
            foul = self.rng.random() < 0.3
            ev_type = "FOUL" if foul else "TACKLE"
            if foul and self.rng.random() < 0.15:
                ev_type = "CARD_YELLOW"
                self.cards.append({"t": self.clock, "team": opp, "player": tackler.name, "card": "YELLOW"})
            ev = Event(
                t=self.clock,
                event_type=ev_type,
                team=opp,
                player=tackler.name,
                x=self.ball[0],
                y=self.ball[1],
                outcome="WON" if not foul else "FOUL",
                extra={"on_player": fouled.name},
            )
            self._lose_possession()
            return ev
        return None

    def _interception(self) -> Optional[Event]:
        if self.rng.random() < 0.05:
            opp = "AWAY" if self.possession == "HOME" else "HOME"
            p = self._pick_player(opp)
            ev = Event(
                t=self.clock, event_type="INTERCEPTION", team=opp, player=p.name,
                x=self.ball[0], y=self.ball[1], outcome="WON",
            )
            self._lose_possession()
            return ev
        return None

    # ---------- main loop

    def run(self, duration_sim_seconds: float = 5400.0, realtime_output: bool = True):
        """Generator of events. `duration_sim_seconds` of simulated play (5400 = 90 min).

        Event density is fixed in simulated time (~25-70 sim seconds between beats,
        roughly 100-150 events per match). `speed` only controls wall-clock pacing:
        speed=1 plays in real time, speed=10 compresses 90 min to 9 min, any large
        speed streams as fast as the consumer reads.
        """
        # kickoff
        yield Event(t=0.0, event_type="MATCH_START", extra={"home": self.teams[0].name, "away": self.teams[1].name})

        self.clock = self.rng.uniform(20, 50)
        while self.clock <= duration_sim_seconds:
            step = self.rng.uniform(15, 45)  # sim seconds until next beat


            last = self.clock
            self.clock += step

            if realtime_output:
                time.sleep(min(step / self.speed, 1.0))

            emitted: list[Event] = []

            # meta
            if last < 2700 <= self.clock and self._half == 1:
                self._half = 2
                emitted.append(Event(t=2700.0, event_type="HALF_END"))
                emitted.append(Event(t=2700.0, event_type="HALF_START"))
            if self.clock > duration_sim_seconds:
                break

            # pressure event first
            ev = self._pressure_event()
            if ev:
                self._pressure_counter -= 1
                emitted.append(ev)

            ev = self._tackle_event()
            if ev:
                emitted.append(ev)
            else:
                ev = self._interception()
                if ev:
                    emitted.append(ev)

            shot = self._maybe_shot()
            if shot:
                emitted.append(shot)

            emitted.append(self._do_pass())

            for e in emitted:
                yield e

        yield Event(t=duration_sim_seconds, event_type="MATCH_END", extra={"score": dict(self.score)})


if __name__ == "__main__":
    import sys

    speed = float(sys.argv[1]) if len(sys.argv) > 1 else 50.0
    sim = MatchSimulator(seed=7, speed=speed)
    for ev in sim.run():
        print(ev.to_json(), flush=True)
