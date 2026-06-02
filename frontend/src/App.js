
import React, { useState, useEffect, useCallback } from "react";

const API = "https://ufc-analytics.onrender.com";

const css = `
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: 'Inter', sans-serif; background: #0d0d10; color: #f0f0f0; }
  .nav { background: #111116; border-bottom: 1px solid #1e1e28; padding: 0 24px; height: 52px; display: flex; align-items: center; justify-content: space-between; position: sticky; top: 0; z-index: 100; }
  .nav-logo { font-size: 17px; font-weight: 700; letter-spacing: -.02em; }
  .nav-logo span { color: #E24B4A; }
  .nav-tabs { display: flex; }
  .nav-tab { font-size: 13px; color: #555; padding: 0 16px; height: 52px; display: flex; align-items: center; border-bottom: 2px solid transparent; cursor: pointer; transition: all .15s; background: none; border-top: none; border-left: none; border-right: none; font-family: inherit; }
  .nav-tab:hover { color: #aaa; }
  .nav-tab.active { color: #f0f0f0; border-bottom-color: #E24B4A; }
  .main { padding: 20px 24px; max-width: 900px; margin: 0 auto; }
  .event-list { display: flex; flex-direction: column; gap: 6px; margin-bottom: 20px; }
  .event-pill { background: #111116; border: 1px solid #1e1e28; border-radius: 8px; padding: 12px 16px; display: flex; align-items: center; justify-content: space-between; cursor: pointer; transition: all .15s; }
  .event-pill:hover { border-color: #E24B4A44; }
  .event-pill.active { border-color: #E24B4A66; }
  .event-pill-name { font-size: 13px; font-weight: 500; color: #ddd; margin-bottom: 2px; }
  .event-pill-meta { font-size: 11px; color: #444; }
  .event-pill-arrow { color: #333; font-size: 16px; }
  .section-label { font-size: 11px; color: #333; text-transform: uppercase; letter-spacing: .08em; font-weight: 500; margin-bottom: 12px; }
  .fight-card { background: #111116; border: 1px solid #1e1e28; border-radius: 12px; padding: 16px 18px; margin-bottom: 8px; }
  .fight-card.main-event { border-color: #E24B4A33; background: #13100f; }
  .main-badge { font-size: 10px; font-weight: 600; color: #E24B4A; letter-spacing: .08em; text-transform: uppercase; margin-bottom: 10px; display: flex; align-items: center; gap: 5px; }
  .fight-row { display: grid; grid-template-columns: 1fr 88px 1fr; align-items: center; margin-bottom: 14px; gap: 8px; }
  .f-left .f-name { font-size: 15px; font-weight: 600; color: #f0f0f0; margin-bottom: 2px; }
  .f-left .f-rec { font-size: 12px; color: #444; }
  .f-right { text-align: right; }
  .f-right .f-name { font-size: 15px; font-weight: 600; color: #f0f0f0; margin-bottom: 2px; }
  .f-right .f-rec { font-size: 12px; color: #444; }
  .f-center { text-align: center; }
  .pick-label { font-size: 9px; color: #333; text-transform: uppercase; letter-spacing: .08em; margin-bottom: 3px; }
  .pick-name { font-size: 13px; font-weight: 600; color: #fff; margin-bottom: 2px; }
  .pick-conf { font-size: 10px; }
  .conf-High { color: #639922; }
  .conf-Medium { color: #BA7517; }
  .conf-Toss-up { color: #444; }
  .bars { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 12px; }
  .bar-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px; }
  .bar-name { font-size: 12px; color: #666; }
  .bar-pct-r { font-size: 12px; font-weight: 600; color: #E24B4A; }
  .bar-pct-b { font-size: 12px; font-weight: 600; color: #378ADD; }
  .bar-pct-dim { font-size: 12px; font-weight: 600; color: #333; }
  .bar-track { height: 3px; background: #1a1a1e; border-radius: 2px; overflow: hidden; }
  .bar-fill-r { height: 100%; background: #E24B4A; border-radius: 2px; }
  .bar-fill-b { height: 100%; background: #378ADD; border-radius: 2px; }
  .fight-actions { display: grid; grid-template-columns: 1fr 1.5fr 1fr; gap: 8px; }
  .btn { height: 32px; border-radius: 7px; font-size: 12px; font-weight: 500; cursor: pointer; display: flex; align-items: center; justify-content: center; gap: 5px; border: 1px solid #222230; background: #16161f; color: #777; transition: all .15s; font-family: inherit; width: 100%; }
  .btn:hover { border-color: #E24B4A55; color: #ccc; background: #1a1a24; }
  .btn-matchup { background: #111118; border-color: #2a2a3a; color: #999; }
  .back-btn { display: flex; align-items: center; gap: 6px; font-size: 12px; color: #444; cursor: pointer; margin-bottom: 16px; background: none; border: none; font-family: inherit; }
  .back-btn:hover { color: #888; }
  .matchup-header { background: #111116; border: 1px solid #1e1e28; border-radius: 12px; padding: 18px; margin-bottom: 12px; }
  .odds-box { background: #111116; border: 1px solid #1e1e28; border-radius: 10px; padding: 14px; margin-bottom: 12px; }
  .odds-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-bottom: 10px; }
  .odds-fighter { background: #0d0d10; border-radius: 7px; padding: 10px 12px; }
  .odds-fname { font-size: 11px; color: #555; margin-bottom: 4px; }
  .odds-line { font-size: 20px; font-weight: 600; color: #f0f0f0; margin-bottom: 2px; }
  .odds-implied { font-size: 11px; color: #444; }
  .verdict-agree { font-size: 12px; font-weight: 500; color: #639922; }
  .verdict-disagree { font-size: 12px; font-weight: 500; color: #BA7517; }
  .h2h { background: #111116; border: 1px solid #1e1e28; border-radius: 10px; padding: 14px; margin-bottom: 12px; }
  .h2h-names { display: grid; grid-template-columns: 1fr 1fr; margin-bottom: 8px; }
  .h2h-name-r { font-size: 13px; font-weight: 600; color: #E24B4A; }
  .h2h-name-b { font-size: 13px; font-weight: 600; color: #378ADD; text-align: right; }
  .h2h-row { display: grid; grid-template-columns: 1fr 110px 1fr; align-items: center; padding: 8px 0; border-top: 1px solid #141418; }
  .h2h-val { font-size: 18px; font-weight: 600; color: #f0f0f0; }
  .h2h-val-b { text-align: right; }
  .h2h-val.winner { color: #f0f0f0; }
  .h2h-label { text-align: center; font-size: 11px; color: #333; text-transform: uppercase; letter-spacing: .05em; }
  .green { color: #639922 !important; }
  .profile-header { background: #111116; border: 1px solid #1e1e28; border-radius: 12px; padding: 18px; margin-bottom: 12px; }
  .profile-name { font-size: 22px; font-weight: 700; margin-bottom: 3px; }
  .profile-meta { font-size: 12px; color: #444; margin-bottom: 14px; }
  .stat-grid { display: grid; grid-template-columns: repeat(4,1fr); gap: 8px; margin-bottom: 14px; }
  .stat-box { background: #0d0d10; border-radius: 7px; padding: 10px; text-align: center; }
  .stat-val { font-size: 20px; font-weight: 600; color: #f0f0f0; margin-bottom: 2px; }
  .stat-lbl { font-size: 10px; color: #444; text-transform: uppercase; letter-spacing: .05em; }
  .tags { display: flex; flex-wrap: wrap; gap: 5px; }
  .tag { background: #161620; border: 1px solid #1e1e28; border-radius: 5px; padding: 3px 9px; font-size: 11px; color: #666; }
  .insights { display: flex; flex-direction: column; gap: 6px; margin-bottom: 12px; }
  .insight { border-left: 2px solid #E24B4A44; padding: 8px 12px; background: #111116; border-radius: 0 7px 7px 0; font-size: 13px; color: #aaa; line-height: 1.5; }
  .fight-log { background: #111116; border: 1px solid #1e1e28; border-radius: 10px; overflow: hidden; }
  .log-row { display: grid; grid-template-columns: 28px 1fr 1fr 40px; gap: 10px; align-items: center; padding: 9px 14px; border-top: 1px solid #141418; font-size: 12px; }
  .log-row:first-child { border-top: none; }
  .w-badge { width: 22px; height: 22px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 10px; font-weight: 600; }
  .w-badge.W { background: #27500A33; color: #639922; }
  .w-badge.L { background: #7F1F1F33; color: #E24B4A; }
  .log-opp { color: #ccc; }
  .log-method { color: #444; }
  .log-rnd { color: #333; text-align: right; }
  .loading { text-align: center; padding: 40px; color: #444; font-size: 14px; }
  .search-wrap { margin-bottom: 16px; }
  .search-input { width: 100%; background: #111116; border: 1px solid #1e1e28; border-radius: 8px; padding: 10px 14px; color: #f0f0f0; font-size: 14px; font-family: inherit; outline: none; transition: border-color .15s; }
  .search-input:focus { border-color: #E24B4A55; }
  .search-results { background: #111116; border: 1px solid #1e1e28; border-radius: 8px; overflow: hidden; margin-top: 4px; }
  .search-result { padding: 10px 14px; font-size: 13px; color: #ccc; cursor: pointer; border-top: 1px solid #141418; transition: background .1s; }
  .search-result:first-child { border-top: none; }
  .search-result:hover { background: #161620; color: #fff; }
  .accuracy-card { background: #111116; border: 1px solid #1e1e28; border-radius: 10px; padding: 14px; margin-bottom: 8px; }
  .accuracy-event { font-size: 13px; font-weight: 500; color: #ddd; margin-bottom: 4px; }
  .accuracy-date { font-size: 11px; color: #444; margin-bottom: 10px; }
  .accuracy-score { font-size: 24px; font-weight: 700; color: #f0f0f0; }
  .accuracy-label { font-size: 11px; color: #444; }
  .metrics { display: grid; grid-template-columns: repeat(3,1fr); gap: 8px; margin-bottom: 16px; }
  .metric-box { background: #111116; border: 1px solid #1e1e28; border-radius: 8px; padding: 12px; text-align: center; }
  .metric-val { font-size: 22px; font-weight: 700; color: #f0f0f0; margin-bottom: 2px; }
  .metric-lbl { font-size: 11px; color: #444; }
`;

function FightCard({ fight, onProfile, onMatchup }) {
  const pred = fight.prediction;
  const pickR = pred && pred.winner === fight.R_fighter;
  return (
    <div className={`fight-card ${fight.is_main ? "main-event" : ""}`}>
      {fight.is_main && <div className="main-badge">★ Main event</div>}
      <div className="fight-row">
        <div className="f-left">
          <div className="f-name">{fight.R_fighter}</div>
          <div className="f-rec">{pred ? "" : "—"}</div>
        </div>
        <div className="f-center">
          <div className="pick-label">Pick</div>
          <div className="pick-name">{pred ? pred.winner.split(" ")[0] : "—"}</div>
          <div className={`pick-conf conf-${pred?.confidence}`}>{pred?.confidence || "—"}</div>
        </div>
        <div className="f-right">
          <div className="f-name">{fight.B_fighter}</div>
        </div>
      </div>
      {pred && (
        <div className="bars">
          <div>
            <div className="bar-head">
              <span className="bar-name">{fight.R_fighter.split(" ")[0]}</span>
              <span className={pickR ? "bar-pct-r" : "bar-pct-dim"}>{pred.prob_r}%</span>
            </div>
            <div className="bar-track"><div className="bar-fill-r" style={{width: pred.prob_r + "%"}} /></div>
          </div>
          <div>
            <div className="bar-head">
              <span className="bar-name">{fight.B_fighter.split(" ")[0]}</span>
              <span className={!pickR ? "bar-pct-b" : "bar-pct-dim"}>{pred.prob_b}%</span>
            </div>
            <div className="bar-track"><div className="bar-fill-b" style={{width: pred.prob_b + "%"}} /></div>
          </div>
        </div>
      )}
      <div className="fight-actions">
        <button className="btn" onClick={() => onProfile(fight.R_fighter, fight.R_link)}>
          👤 {fight.R_fighter.split(" ")[0]}
        </button>
        <button className="btn btn-matchup" onClick={() => onMatchup(fight)}>
          ⚔ Full matchup
        </button>
        <button className="btn" onClick={() => onProfile(fight.B_fighter, fight.B_link)}>
          👤 {fight.B_fighter.split(" ")[0]}
        </button>
      </div>
    </div>
  );
}

function EventsPage({ onProfile, onMatchup }) {
  const [events, setEvents] = useState([]);
  const [selectedIdx, setSelectedIdx] = useState(null);
  const [card, setCard] = useState(null);
  const [loadingCard, setLoadingCard] = useState(false);

  useEffect(() => {
    fetch(`${API}/events`).then(r => r.json()).then(data => {
      setEvents(data);
    });
  }, []);

  const selectEvent = (i) => {
    if (selectedIdx === i) {
      setSelectedIdx(null);
      setCard(null);
      return;
    }
    setSelectedIdx(i);
    setLoadingCard(true);
    setCard(null);
    fetch(`${API}/events/${i}/card`)
      .then(r => r.json())
      .then(data => { setCard(data); setLoadingCard(false); });
  };

  return (
    <div>
      {events.map((ev, i) => (
        <div key={i}>
          <div
            className={`event-pill ${i === selectedIdx ? "active" : ""}`}
            onClick={() => selectEvent(i)}
            style={{marginBottom: i === selectedIdx ? 8 : 6}}
          >
            <div>
              <div className="event-pill-name">{ev.name}</div>
              <div className="event-pill-meta">{ev.date} · {ev.location?.split(",")[0]}</div>
            </div>
            <span className="event-pill-arrow">{i === selectedIdx ? "∨" : "›"}</span>
          </div>
          {i === selectedIdx && (
            <div style={{marginBottom:16}}>
              {loadingCard && <div className="loading">Loading card...</div>}
              {card && card.fights?.map((fight, j) => (
                <FightCard key={j} fight={fight} onProfile={onProfile} onMatchup={onMatchup} />
              ))}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

function MatchupPage({ fight, onBack, onProfile }) {
  const [pred, setPred] = useState(fight?.prediction || null);
  const [stats_r, setStatsR] = useState(null);
  const [stats_b, setStatsB] = useState(null);

  useEffect(() => {
    if (!fight) return;
    if (!pred) {
      fetch(`${API}/predict?fighter_r=${encodeURIComponent(fight.R_fighter)}&fighter_b=${encodeURIComponent(fight.B_fighter)}`)
        .then(r => r.json()).then(setPred);
    }
    fetch(`${API}/stats?name=${encodeURIComponent(fight.R_fighter)}`).then(r=>r.json()).then(setStatsR);
    fetch(`${API}/stats?name=${encodeURIComponent(fight.B_fighter)}`).then(r=>r.json()).then(setStatsB);
  }, [fight]);

  if (!fight) return <div className="loading">Select a fight from the Events tab.</div>;

  const H2HRow = ({label, vr, vb, nr, nb}) => (
    <div className="h2h-row">
      <div className={`h2h-val ${nr > nb ? "green" : ""}`}>{vr}</div>
      <div className="h2h-label">{label}</div>
      <div className={`h2h-val h2h-val-b ${nb > nr ? "green" : ""}`}>{vb}</div>
    </div>
  );

  return (
    <div>
      <button className="back-btn" onClick={onBack}>← Back</button>
      <div style={{fontSize:15,fontWeight:600,marginBottom:16}}>{fight.R_fighter} vs {fight.B_fighter}</div>
      <div className="matchup-header">
        <div className="fight-row" style={{marginBottom:14}}>
          <div className="f-left">
            <div className="f-name">{fight.R_fighter}</div>
            <div className="f-rec">{stats_r ? `${stats_r.wins}W · ${stats_r.losses}L` : ""}</div>
          </div>
          <div className="f-center">
            <div className="pick-label">Prediction</div>
            <div className="pick-name" style={{fontSize:15}}>{pred?.winner?.split(" ")[0] || "—"}</div>
            <div className={`pick-conf conf-${pred?.confidence}`}>{pred?.confidence || ""}</div>
          </div>
          <div className="f-right">
            <div className="f-name">{fight.B_fighter}</div>
            <div className="f-rec">{stats_b ? `${stats_b.wins}W · ${stats_b.losses}L` : ""}</div>
          </div>
        </div>
        {pred && (
          <div className="bars">
            <div>
              <div className="bar-head"><span className="bar-name">{fight.R_fighter.split(" ")[0]}</span><span className="bar-pct-r" style={{fontSize:14}}>{pred.prob_r}%</span></div>
              <div className="bar-track" style={{height:5}}><div className="bar-fill-r" style={{width:pred.prob_r+"%",height:"100%"}} /></div>
            </div>
            <div>
              <div className="bar-head"><span className="bar-name">{fight.B_fighter.split(" ")[0]}</span><span className="bar-pct-b" style={{fontSize:14}}>{pred.prob_b}%</span></div>
              <div className="bar-track" style={{height:5}}><div className="bar-fill-b" style={{width:pred.prob_b+"%",height:"100%"}} /></div>
            </div>
          </div>
        )}
      </div>
      {pred?.r_odds && pred?.b_odds && (
        <div className="odds-box">
          <div className="section-label" style={{marginBottom:10}}>Model vs. betting market</div>
          <div className="odds-grid">
            <div className="odds-fighter">
              <div className="odds-fname">{fight.R_fighter}</div>
              <div className="odds-line">{pred.r_odds > 0 ? "+" : ""}{pred.r_odds}</div>
              <div className="odds-implied">{pred.r_implied}% implied</div>
            </div>
            <div className="odds-fighter">
              <div className="odds-fname">{fight.B_fighter}</div>
              <div className="odds-line">{pred.b_odds > 0 ? "+" : ""}{pred.b_odds}</div>
              <div className="odds-implied">{pred.b_implied}% implied</div>
            </div>
          </div>
          <div className={pred.agrees_market ? "verdict-agree" : "verdict-disagree"}>
            {pred.agrees_market ? "✓ Model agrees with the betting market" : "⚡ Model DISAGREES — sees an upset"}
          </div>
        </div>
      )}
      {stats_r && stats_b && !stats_r.error && !stats_b.error && (
        <div className="h2h">
          <div className="section-label" style={{marginBottom:8}}>Head-to-head</div>
          <div className="h2h-names">
            <div className="h2h-name-r">{fight.R_fighter}</div>
            <div className="h2h-name-b">{fight.B_fighter}</div>
          </div>
          <H2HRow label="Record" vr={`${stats_r.wins}-${stats_r.losses}`} vb={`${stats_b.wins}-${stats_b.losses}`} nr={stats_r.wins} nb={stats_b.wins} />
          <H2HRow label="KO wins" vr={stats_r.ko_wins} vb={stats_b.ko_wins} nr={stats_r.ko_wins} nb={stats_b.ko_wins} />
          <H2HRow label="Sub wins" vr={stats_r.sub_wins} vb={stats_b.sub_wins} nr={stats_r.sub_wins} nb={stats_b.sub_wins} />
          <H2HRow label="Striking %" vr={`${stats_r.sig_str_pct}%`} vb={`${stats_b.sig_str_pct}%`} nr={stats_r.sig_str_pct} nb={stats_b.sig_str_pct} />
          <H2HRow label="Takedown %" vr={`${stats_r.td_pct}%`} vb={`${stats_b.td_pct}%`} nr={stats_r.td_pct} nb={stats_b.td_pct} />
          <H2HRow label="Win streak" vr={stats_r.win_streak} vb={stats_b.win_streak} nr={stats_r.win_streak} nb={stats_b.win_streak} />
          <H2HRow label="Height cm" vr={stats_r.height_cm} vb={stats_b.height_cm} nr={stats_r.height_cm} nb={stats_b.height_cm} />
          <H2HRow label="Reach cm" vr={stats_r.reach_cm} vb={stats_b.reach_cm} nr={stats_r.reach_cm} nb={stats_b.reach_cm} />
        </div>
      )}
      <div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:8,marginTop:12}}>
        <button className="btn" style={{height:38,fontSize:13}} onClick={() => onProfile(fight.R_fighter, fight.R_link)}>👤 {fight.R_fighter} profile</button>
        <button className="btn" style={{height:38,fontSize:13}} onClick={() => onProfile(fight.B_fighter, fight.B_link)}>👤 {fight.B_fighter} profile</button>
      </div>
    </div>
  );
}


function FighterPage({ name, url, onBack }) {
  const [profile, setProfile] = useState(null);

  useEffect(() => {
    if (!url) return;
    fetch(`${API}/fighter?url=${encodeURIComponent(url)}`).then(r => r.json()).then(setProfile);
  }, [url]);

  if (!profile) return <div className="loading">Loading fighter profile...</div>;
  const wins = profile.fights?.filter(f => f.result === "win") || [];
  const finishRate = wins.length ? Math.round(wins.filter(f => ["KO/TKO","Submission"].some(m => f.method?.includes(m.split("/")[0]))).length / wins.length * 100) : 0;

  return (
    <div>
      <button className="back-btn" onClick={onBack}>← Back</button>
      <div className="profile-header">
        <div className="profile-name">{profile.name}</div>
        <div className="profile-meta">
          {[profile.weight_class, profile.age && `${profile.age} yrs`, profile.height_cm && `${profile.height_cm}cm`, profile.reach_cm && `${profile.reach_cm}cm reach`].filter(Boolean).join(" · ")}
        </div>
        <div className="stat-grid">
          <div className="stat-box"><div className="stat-val">{profile.wins}</div><div className="stat-lbl">Wins</div></div>
          <div className="stat-box"><div className="stat-val">{profile.losses}</div><div className="stat-lbl">Losses</div></div>
          <div className="stat-box"><div className="stat-val">{finishRate}%</div><div className="stat-lbl">Finish rate</div></div>
          <div className="stat-box"><div className="stat-val">{profile.fights?.length || 0}</div><div className="stat-lbl">Pro fights</div></div>
        </div>
        {profile.tags?.length > 0 && (
          <div className="tags">{profile.tags.map((t,i) => <span key={i} className="tag">{t}</span>)}</div>
        )}
      </div>
      {profile.insights?.length > 0 && (
        <>
          <div className="section-label">Fighter insights</div>
          <div className="insights">
            {profile.insights.map((ins,i) => <div key={i} className="insight">{ins}</div>)}
          </div>
        </>
      )}
      <div className="section-label">Fight history</div>
      <div className="fight-log">
        {profile.fights?.slice(0,10).map((f,i) => (
          <div key={i} className="log-row">
            <div className={`w-badge ${f.result === "win" ? "W" : "L"}`}>{f.result === "win" ? "W" : "L"}</div>
            <div className="log-opp">{f.opponent}</div>
            <div className="log-method">{f.method}</div>
            <div className="log-rnd">R{f.round}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

function AccuracyPage() {
  const [history, setHistory] = useState([]);
  useEffect(() => { fetch(`${API}/accuracy`).then(r=>r.json()).then(setHistory); }, []);
  const total_correct = history.reduce((s,e) => s+e.correct, 0);
  const total_fights = history.reduce((s,e) => s+e.total, 0);
  const overall = total_fights ? Math.round(total_correct/total_fights*100) : 0;
  const total_disagree = history.reduce((s,e) => s+(e.disagree_total||0), 0);
  const disagree_correct = history.reduce((s,e) => s+(e.disagree_correct||0), 0);
  const edge = total_disagree ? Math.round(disagree_correct/total_disagree*100) : null;

  return (
    <div>
      <div className="metrics">
        <div className="metric-box"><div className="metric-val">{overall}%</div><div className="metric-lbl">Overall accuracy</div></div>
        <div className="metric-box"><div className="metric-val">{total_correct}/{total_fights}</div><div className="metric-lbl">Correct picks</div></div>
        <div className="metric-box"><div className="metric-val">{edge !== null ? edge+"%" : "—"}</div><div className="metric-lbl">Edge vs market</div></div>
      </div>
      <div className="section-label">Event history</div>
      {history.map((ev, i) => (
        <div key={i} className="accuracy-card">
          <div className="accuracy-event">{ev.event}</div>
          <div className="accuracy-date">{ev.date}</div>
          <div style={{display:"flex",alignItems:"baseline",gap:8}}>
            <div className="accuracy-score">{ev.correct}/{ev.total}</div>
            <div style={{fontSize:14,color: ev.accuracy >= 65 ? "#639922" : ev.accuracy >= 50 ? "#BA7517" : "#E24B4A",fontWeight:600}}>{ev.accuracy}%</div>
          </div>
        </div>
      ))}
      {history.length === 0 && <div className="loading">No events tracked yet.</div>}
    </div>
  );
}

export default function App() {
  const [tab, setTab] = useState("events");
  const [selectedFight, setSelectedFight] = useState(null);
  const [selectedFighter, setSelectedFighter] = useState(null);
  const [prevTab, setPrevTab] = useState("events");

  const goProfile = (name, url) => {
    setPrevTab(tab);
    setSelectedFighter({ name, url });
    setTab("fighter");
  };

  const goMatchup = (fight) => {
    setPrevTab(tab);
    setSelectedFight(fight);
    setTab("matchup");
  };

  const goBack = () => setTab(prevTab);

  return (
    <>
      <style>{css}</style>
      <div className="nav">
        <div className="nav-logo">UFC<span>analytics</span></div>
        <div className="nav-tabs">
          {["events","matchup","accuracy"].map(t => (
            <button key={t} className={`nav-tab ${tab===t?"active":""}`} onClick={() => setTab(t)}>
              {t.charAt(0).toUpperCase()+t.slice(1)}
            </button>
          ))}
        </div>
      </div>
      <div className="main">
        {tab === "events" && <EventsPage onProfile={goProfile} onMatchup={goMatchup} />}
        {tab === "matchup" && <MatchupPage fight={selectedFight} onBack={goBack} onProfile={goProfile} />}
        {tab === "fighter" && <FighterPage name={selectedFighter?.name} url={selectedFighter?.url} onBack={goBack} />}
        {tab === "accuracy" && <AccuracyPage />}
      </div>
    </>
  );
}
