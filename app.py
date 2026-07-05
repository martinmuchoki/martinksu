
from flask import Flask, render_template_string, request, send_file
from pathlib import Path
import pandas as pd, numpy as np
import plotly.graph_objects as go
import plotly.io as pio
from datetime import datetime

app=Flask(__name__)
DATA=Path("prices.csv")
MASTER=Path("symbol_master.csv")
FUND=Path("fundamentals.csv")
PORTFOLIO=Path("portfolio.csv")
CHAT_LOG=Path("ai_advisor_chat_log_v9_1.csv")
REPORT=Path("ai_advisor_report_v9_1.txt")
CAPITAL=20000

CSS='body{font-family:Arial;margin:22px;background:#f2f6f3}h1,h2{color:#126b3a}.note{background:#fff3cd;padding:12px;border-left:5px solid #ffc107;margin:14px 0}.box{background:white;padding:15px;border-radius:9px;box-shadow:0 1px 5px #ccc;margin-bottom:15px}textarea{width:100%;height:75px;padding:10px}button,.button{background:#126b3a;color:white;padding:9px 12px;border-radius:6px;text-decoration:none;border:0;display:inline-block;margin:5px 5px 12px 0}table{border-collapse:collapse;width:100%;background:white;margin-bottom:20px}th,td{border:1px solid #ddd;padding:8px;text-align:center;font-size:12px}th{background:#126b3a;color:white}pre{white-space:pre-wrap;background:white;padding:15px;border-radius:9px}.BUY,.STRONG{color:green;font-weight:bold}.SELL{color:red;font-weight:bold}.WATCH{color:#b8860b;font-weight:bold}'

def load_prices():
    df=pd.read_csv(DATA)
    df["date"]=pd.to_datetime(df["date"])
    df["symbol"]=df["symbol"].astype(str).str.upper().str.strip()
    df["close"]=pd.to_numeric(df["close"],errors="coerce")
    df["volume"]=pd.to_numeric(df["volume"],errors="coerce").fillna(0)
    return df.dropna().sort_values(["symbol","date"])

def master():
    return pd.read_csv(MASTER).set_index("symbol").to_dict("index")

def fund():
    df=pd.read_csv(FUND)
    return {r.symbol:r for r in df.itertuples()}

def pivot():
    return load_prices().pivot(index="date",columns="symbol",values="close").sort_index().ffill()

def returns():
    return pivot().pct_change().dropna()

def stock_metrics():
    df=load_prices()
    mm=master(); ff=fund()
    rows=[]
    for sym,g in df.groupby("symbol"):
        g=g.sort_values("date").copy()
        g["ma20"]=g.close.rolling(20,min_periods=1).mean()
        g["ma50"]=g.close.rolling(50,min_periods=1).mean()
        last=g.iloc[-1]
        close=float(last.close)
        ret5=(close/g.close.iloc[-6]-1)*100 if len(g)>6 else 0
        ret20=(close/g.close.iloc[-21]-1)*100 if len(g)>21 else 0
        vol=g.close.pct_change().tail(60).std()*np.sqrt(252)*100
        mom=60
        if close>last.ma20>last.ma50: mom+=25
        elif close<last.ma20: mom-=20
        if ret20>5: mom+=10
        if ret5>2: mom+=5
        mom=max(0,min(100,mom))
        fu=ff.get(sym,None)
        fscore=float(getattr(fu,"fundamental_score",50)) if fu else 50
        dy=float(getattr(fu,"dividend_yield",0)) if fu else 0
        ai=max(0,min(100,mom*.45 + fscore*.35 + min(max(ret20+20,0),40)*.4 + dy*1.2 - min(vol,80)*.15))
        signal="STRONG BUY" if ai>=82 else "BUY" if ai>=72 else "WATCH" if ai>=50 else "SELL"
        risk="LOW" if vol<25 else "HIGH" if vol>45 else "MEDIUM"
        rows.append({"symbol":sym,"company":mm.get(sym,{}).get("company",sym),"sector":mm.get(sym,{}).get("sector","Unknown"),"close":round(close,2),"return_5d":round(ret5,2),"return_20d":round(ret20,2),"volatility":round(vol,2),"momentum_score":round(mom,1),"fundamental_score":fscore,"dividend_yield":dy,"ai_score":round(ai,1),"signal":signal,"risk":risk})
    return sorted(rows,key=lambda x:x["ai_score"],reverse=True)

def sector_rotation():
    df=pd.DataFrame(stock_metrics())
    sec=df.groupby("sector").agg(avg_ai=("ai_score","mean"),avg_20d=("return_20d","mean"),avg_div=("dividend_yield","mean"),stocks=("symbol","count")).reset_index()
    sec["rating"]=sec.apply(lambda r:"OVERWEIGHT" if r.avg_ai>=70 and r.avg_20d>0 else "UNDERWEIGHT" if r.avg_ai<50 else "NEUTRAL",axis=1)
    return sec.sort_values("avg_ai",ascending=False).round(2).to_dict("records")

def market_regime():
    rows=stock_metrics()
    avg_ai=np.mean([r["ai_score"] for r in rows])
    avg20=np.mean([r["return_20d"] for r in rows])
    adv=sum(1 for r in rows if r["return_5d"]>0)
    dec=sum(1 for r in rows if r["return_5d"]<0)
    above=sum(1 for r in rows if r["momentum_score"]>=70)
    score=50
    score+=20 if avg20>3 else 8 if avg20>0 else -15
    score+=20 if above/len(rows)>0.55 else -10
    score+=15 if avg_ai>65 else -10 if avg_ai<50 else 5
    score+=10 if adv>dec else -8
    conf=max(0,min(100,score))
    regime="BULL MARKET" if conf>=70 else "BEAR MARKET" if conf<=40 else "SIDEWAYS MARKET"
    exposure=75 if regime=="BULL MARKET" else 35 if regime=="BEAR MARKET" else 55
    return {"regime":regime,"confidence":round(conf,1),"stock_exposure":exposure,"cash":100-exposure,"advancers":adv,"decliners":dec,"avg_ai":round(avg_ai,1),"avg_20d":round(avg20,2)}

def portfolio():
    lp={r["symbol"]:r["close"] for r in stock_metrics()}
    mm=master()
    pf=pd.read_csv(PORTFOLIO)
    rows=[]; total=0
    for _,p in pf.iterrows():
        sym=str(p.symbol).upper()
        shares=float(p.shares); buy=float(p.buy_price); cur=float(lp.get(sym,0))
        value=shares*cur; total+=value
        rows.append({"symbol":sym,"company":mm.get(sym,{}).get("company",sym),"sector":mm.get(sym,{}).get("sector","Unknown"),"shares":int(shares),"value":round(value,2),"profit":round(value-shares*buy,2)})
    for r in rows: r["weight"]=round(r["value"]/total*100,2) if total else 0
    return rows,round(total,2)

def dividend_portfolio(capital=CAPITAL):
    rows=sorted(stock_metrics(),key=lambda x:(x["dividend_yield"],x["ai_score"]),reverse=True)[:5]
    weight=1/len(rows)
    out=[]
    for r in rows:
        amount=capital*weight
        shares=int(amount//r["close"]) if r["close"] else 0
        actual=shares*r["close"]
        out.append({**r,"target_amount":round(amount,2),"shares":shares,"actual_amount":round(actual,2),"expected_dividend":round(actual*r["dividend_yield"]/100,2)})
    return out

def allocation_advice():
    rows=stock_metrics()
    top=[r for r in rows if r["signal"] in ["BUY","STRONG BUY"]][:5]
    reg=market_regime()
    exposure=reg["stock_exposure"]/100
    invest=CAPITAL*exposure
    cash=CAPITAL-invest
    weight=1/len(top) if top else 0
    out=[]
    for r in top:
        amount=invest*weight
        shares=int(amount//r["close"]) if r["close"] else 0
        out.append({**r,"target_amount":round(amount,2),"shares":shares})
    return out,round(cash,2)

def answer_question(q):
    ql=q.lower()
    rows=stock_metrics()
    reg=market_regime()
    sectors=sector_rotation()
    holdings,total=portfolio()
    answer=[]
    if "best" in ql or "buy" in ql or "top" in ql:
        answer.append("Top NSE opportunities based on AI score:")
        for r in rows[:5]:
            answer.append(f"- {r['symbol']} ({r['company']}): {r['signal']} | AI {r['ai_score']} | Risk {r['risk']} | 20D return {r['return_20d']}%")
        answer.append("")
        answer.append("Why: these rank highest after combining momentum, fundamentals, dividend yield and volatility.")
    elif "bank" in ql or "sector" in ql or "exposure" in ql:
        answer.append("Sector recommendation:")
        for s in sectors[:5]:
            answer.append(f"- {s['sector']}: {s['rating']} | Avg AI {s['avg_ai']} | 20D {s['avg_20d']}%")
        answer.append("")
        answer.append(f"Current market regime is {reg['regime']}; suggested stock exposure is {reg['stock_exposure']}%.")
    elif "dividend" in ql:
        div=dividend_portfolio()
        total_div=sum(x["expected_dividend"] for x in div)
        answer.append(f"Dividend portfolio for KSh {CAPITAL}:")
        for r in div:
            answer.append(f"- {r['symbol']}: {r['shares']} shares | KSh {r['actual_amount']} | Yield {r['dividend_yield']}% | Est dividend KSh {r['expected_dividend']}")
        answer.append(f"Estimated annual dividend income: KSh {round(total_div,2)}")
    elif "risk" in ql or "safe" in ql or "lowest" in ql:
        safe=sorted(rows,key=lambda x:(x["risk"]!="LOW",x["volatility"]))[:5]
        answer.append("Lowest-risk candidates:")
        for r in safe:
            answer.append(f"- {r['symbol']}: Risk {r['risk']} | Volatility {r['volatility']}% | AI {r['ai_score']} | Signal {r['signal']}")
    elif "portfolio" in ql or "allocate" in ql:
        alloc,cash=allocation_advice()
        answer.append(f"Suggested allocation for KSh {CAPITAL}:")
        for r in alloc:
            answer.append(f"- {r['symbol']}: KSh {r['target_amount']} | {r['shares']} shares | Signal {r['signal']} | AI {r['ai_score']}")
        answer.append(f"- Cash reserve: KSh {cash}")
    else:
        answer.append(f"Market regime: {reg['regime']} ({reg['confidence']}%).")
        answer.append(f"Recommended exposure: Stocks {reg['stock_exposure']}%, Cash {reg['cash']}%.")
        answer.append("Try asking: best stocks to buy, safest stocks, dividend portfolio, banking exposure, or portfolio allocation.")
    final="\n".join(answer)
    log_row={"time":datetime.now().strftime("%Y-%m-%d %H:%M:%S"),"question":q,"answer":final}
    if CHAT_LOG.exists():
        df=pd.read_csv(CHAT_LOG)
        df=pd.concat([df,pd.DataFrame([log_row])],ignore_index=True)
    else:
        df=pd.DataFrame([log_row])
    df.to_csv(CHAT_LOG,index=False)
    return final

def report_text():
    reg=market_regime()
    top=stock_metrics()[:5]
    sectors=sector_rotation()[:5]
    txt=["NSE AI INVESTMENT ADVISOR REPORT",f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}",""]
    txt.append(f"Market Regime: {reg['regime']} ({reg['confidence']}%)")
    txt.append(f"Recommended Exposure: Stocks {reg['stock_exposure']}%, Cash {reg['cash']}%")
    txt.append("")
    txt.append("Top Picks:")
    for r in top: txt.append(f"- {r['symbol']} | {r['signal']} | AI {r['ai_score']} | Risk {r['risk']}")
    txt.append("")
    txt.append("Sector View:")
    for s in sectors: txt.append(f"- {s['sector']} | {s['rating']} | Avg AI {s['avg_ai']}")
    REPORT.write_text("\n".join(txt),encoding="utf-8")
    return "\n".join(txt)

def chart_html():
    rows=stock_metrics()[:10]
    fig=go.Figure()
    fig.add_trace(go.Bar(x=[r["symbol"] for r in rows],y=[r["ai_score"] for r in rows],name="AI Score"))
    fig.update_layout(title="Top AI Scores",height=450,template="plotly_white")
    return pio.to_html(fig,full_html=False,include_plotlyjs="cdn")

def page(title,body):
    return f"<!doctype html><html><head><title>{title}</title><style>{CSS}</style></head><body>{body}</body></html>"

@app.route("/",methods=["GET","POST"])
def index():
    response=""
    question=""
    if request.method=="POST":
        question=request.form.get("question","")
        response=answer_question(question)
    reg=market_regime()
    body=render_template_string("""
<h1>NSE Signal Bot V9.1 — Conversational AI Investment Advisor</h1>
<div class='note'>Ask questions like: best stocks to buy, dividend portfolio, safest stocks, banking exposure, portfolio allocation.</div>
<a class='button' href='/screener'>AI Screener</a><a class='button' href='/portfolio'>Portfolio Advice</a><a class='button' href='/dividends'>Dividend Builder</a><a class='button' href='/report'>Daily Report</a><a class='button' href='/charts'>Charts</a>
<div class='box'>
<h2>Ask the AI Advisor</h2>
<form method='post'>
<textarea name='question' placeholder='Example: What are the best NSE stocks to buy today?'>{{question}}</textarea><br>
<button type='submit'>Ask Advisor</button>
</form>
{% if response %}<h2>Advisor Answer</h2><pre>{{response}}</pre>{% endif %}
</div>
<div class='box'><h2>Market Status</h2>
<p><b>{{reg.regime}}</b> — Confidence {{reg.confidence}}%</p>
<p>Recommended: Stocks {{reg.stock_exposure}}%, Cash {{reg.cash}}%</p>
</div>
""",question=question,response=response,reg=reg)
    return page("NSE Bot V9.1",body)

@app.route("/screener")
def screener():
    return page("AI Screener","<h1>AI Stock Screener</h1><p><a class='button' href='/'>Back</a></p>"+pd.DataFrame(stock_metrics()).to_html(index=False))

@app.route("/portfolio")
def port():
    alloc,cash=allocation_advice()
    h,total=portfolio()
    body=f"<h1>Portfolio Advice</h1><p><a class='button' href='/'>Back</a></p><h2>Current Portfolio: KSh {total}</h2>"+pd.DataFrame(h).to_html(index=False)+"<h2>Suggested Allocation</h2>"+pd.DataFrame(alloc).to_html(index=False)+f"<h3>Cash Reserve: KSh {cash}</h3>"
    return page("Portfolio Advice",body)

@app.route("/dividends")
def divs():
    div=dividend_portfolio()
    total=sum(x["expected_dividend"] for x in div)
    return page("Dividend Builder",f"<h1>Dividend Portfolio Builder</h1><p><a class='button' href='/'>Back</a></p><h2>Estimated annual dividend: KSh {round(total,2)}</h2>"+pd.DataFrame(div).to_html(index=False))

@app.route("/report")
def report():
    return page("Daily Report","<h1>AI Investment Report</h1><p><a class='button' href='/'>Back</a> <a class='button' href='/download_report'>Download</a></p><pre>"+report_text()+"</pre>")

@app.route("/download_report")
def download_report():
    report_text()
    return send_file(REPORT,as_attachment=True)

@app.route("/charts")
def charts():
    return page("Charts","<p><a class='button' href='/'>Back</a></p>"+chart_html())

if __name__=="__main__":
    print("Open Chrome: http://127.0.0.1:5000")
    app.run(debug=True)
