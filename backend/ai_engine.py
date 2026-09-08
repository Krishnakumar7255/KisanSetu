"""Lightweight, dependency-free predictive engine for KisanSetu.
Uses ridge regression trained on completed operational records when enough history exists;
otherwise it uses a cold-start model derived from queue/counter features.
"""
from datetime import datetime, timedelta
import math

SLOTS = ["08:00 - 10:00","10:00 - 12:00","12:00 - 14:00","14:00 - 16:00","16:00 - 18:00"]


def slot_start(slot):
    try:
        t = datetime.strptime(slot.split('-')[0].strip(), '%H:%M').time()
        return t.hour * 60 + t.minute
    except Exception:
        return 0


def features(*, ahead, counters, quantity, slot, checked_in=False, hour=None):
    hour = datetime.now().hour if hour is None else hour
    slot_idx = SLOTS.index(slot) if slot in SLOTS else 0
    return [1.0, float(ahead), 1.0/max(1, counters), math.log1p(max(0, quantity))/5.0,
            1.0 if checked_in else 0.0, slot_idx/4.0, hour/23.0]


def fit_ridge(samples, alpha=0.8, epochs=1200, lr=0.015):
    if len(samples) < 3:
        return None
    n = len(samples); d = len(samples[0][0])
    w = [0.0] * d
    # sensible intercept for cold-start learning
    w[0] = 5.0
    for _ in range(epochs):
        grad = [0.0] * d
        for x, y in samples:
            pred = sum(a*b for a,b in zip(x,w))
            err = pred - y
            for j in range(d): grad[j] += err*x[j]
        for j in range(d):
            reg = 0.0 if j == 0 else alpha*w[j]
            w[j] -= lr * ((2.0/n)*grad[j] + reg)
    return w


def predict(w, x):
    return max(2.0, round(sum(a*b for a,b in zip(x,w)), 1))


def build_model(bookings, counters):
    samples=[]
    for b in bookings:
        called=b.get('called_at'); created=b.get('created_at')
        if not called or not created: continue
        try:
            wait=max(0,(datetime.fromisoformat(called.replace('Z','+00:00'))-
                        datetime.fromisoformat(created.replace('Z','+00:00'))).total_seconds()/60)
        except Exception:
            try:
                wait=max(0,(datetime.fromisoformat(called)-datetime.fromisoformat(created)).total_seconds()/60)
            except Exception: continue
        if wait > 480: continue
        x=features(ahead=0,counters=counters,quantity=float(b.get('quantity_kg') or 0),
                   slot=b.get('slot','08:00 - 10:00'),checked_in=bool(b.get('checked_in')))
        # Historical record is a service-time observation; include a conservative queue proxy.
        x[1]=1.0
        samples.append((x, wait))
    w=fit_ridge(samples)
    return w, len(samples)


def explain(ahead, counters, checked_in, slot):
    reasons=[]
    if ahead >= 5: reasons.append(f"{ahead} farmers ahead")
    elif ahead: reasons.append(f"{ahead} farmer(s) ahead")
    if counters <= 1: reasons.append("single active counter")
    elif counters >= 3: reasons.append(f"{counters} active counters")
    if checked_in: reasons.append("farmer already checked in")
    reasons.append(f"slot {slot}")
    return reasons


def _parse_dt(v):
    if not v: return None
    try: return datetime.fromisoformat(str(v).replace('Z','+00:00')).replace(tzinfo=None)
    except Exception: return None


def operational_insights(bookings, counters, now=None):
    """Explainable AI-style operational intelligence using historical + live signals.
    No external model/API is required, so the demo works offline as well.
    """
    now = now or datetime.now()
    active = [b for b in bookings if b.get('status') in ('waiting','serving','procurement_pending')]
    today = [b for b in bookings if b.get('date') == now.date().isoformat()]
    completed = [b for b in bookings if b.get('status') == 'completed']
    waits=[]; service=[]
    for b in completed + bookings:
        c=_parse_dt(b.get('called_at')); created=_parse_dt(b.get('created_at'))
        done=_parse_dt(b.get('completed_at'))
        if c and created:
            w=(c-created).total_seconds()/60
            if 0 <= w <= 480: waits.append(w)
        if c and done:
            m=(done-c).total_seconds()/60
            if 1 <= m <= 60: service.append(m)
    avg_wait=round(sum(waits)/len(waits),1) if waits else 5.0
    avg_service=round(sum(service)/len(service),1) if service else 5.0
    capacity=max(1,int(counters))*10
    utilization=round(min(100,len(active)/capacity*100))
    load_score=min(100, round(utilization*0.55 + min(100,len(active)*6)*0.45))
    risk='Low'
    if load_score >= 75: risk='High'
    elif load_score >= 45: risk='Medium'

    # Short-horizon demand forecast: recent daily counts with recency weighting.
    day_counts={}
    for b in bookings:
        d=b.get('date')
        if d: day_counts[d]=day_counts.get(d,0)+1
    forecast=0.0; weight_sum=0.0
    for i in range(1,8):
        d=(now.date()-timedelta(days=i)).isoformat(); w=8-i
        forecast += day_counts.get(d,0)*w; weight_sum += w
    forecast=round(forecast/weight_sum,1) if weight_sum else float(len(today))
    forecast=max(forecast, len(today))

    # Quantity pressure helps procurement planning.
    qty=sum(float(b.get('quantity_kg') or 0) for b in active)
    avg_qty=sum(float(b.get('quantity_kg') or 0) for b in bookings if b.get('quantity_kg'))/max(1,sum(1 for b in bookings if b.get('quantity_kg')))
    heavy_ratio=round(sum(1 for b in active if float(b.get('quantity_kg') or 0)>max(500,avg_qty*1.5))/max(1,len(active))*100)

    alerts=[]
    if risk=='High': alerts.append('Queue congestion risk is high — open an additional counter if available.')
    elif risk=='Medium': alerts.append('Queue is building — stagger upcoming arrivals to avoid a peak.')
    else: alerts.append('Queue load is currently manageable.')
    if heavy_ratio >= 30: alerts.append('High-quantity farmers may increase service time; prioritize counter readiness.')
    if forecast > len(today)+3: alerts.append('Demand forecast is above today\'s current load; prepare staff/counters.')
    if not alerts: alerts.append('No immediate operational alert.')

    return {
        'risk_level': risk, 'congestion_score': load_score, 'active_tokens': len(active),
        'today_bookings': len(today), 'forecast_next_day': forecast,
        'avg_wait_min': avg_wait, 'avg_service_min': avg_service,
        'active_quantity_kg': round(qty,1), 'heavy_load_percent': heavy_ratio,
        'recommended_counters': max(1, min(20, math.ceil(max(1,forecast)/10))),
        'alerts': alerts,
        'model': 'Explainable ensemble (queue load + recency-weighted demand + service history)',
        'training_samples': len(waits)+len(service)
    }


def anomaly_flags(bookings):
    """Flag unusual operational records for an operator review."""
    vals=[]
    for b in bookings:
        c=_parse_dt(b.get('called_at')); created=_parse_dt(b.get('created_at'))
        if c and created:
            v=(c-created).total_seconds()/60
            if 0 <= v <= 480: vals.append((b,v))
    if len(vals)<4: return []
    mean=sum(v for _,v in vals)/len(vals)
    sd=(sum((v-mean)**2 for _,v in vals)/len(vals))**0.5
    threshold=max(mean+2*sd, mean*2.5, 30)
    out=[]
    for b,v in vals:
        if v>threshold:
            out.append({'token':b.get('token'),'wait_min':round(v,1),'reason':'Unusually long wait compared with centre history'})
    return out[:8]
