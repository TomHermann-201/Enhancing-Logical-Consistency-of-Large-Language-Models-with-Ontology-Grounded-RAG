"""
app.py
Streamlit Web UI for OV-RAG Prototype

Simplified 3-page app with clear explanations of each pipeline step.
"""

import contextlib
import io
import json
import os
import tempfile
import time
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="OV-RAG Prototype",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Cached resources
# ---------------------------------------------------------------------------

@st.cache_resource
def get_validator():
    captured = io.StringIO()
    with contextlib.redirect_stdout(captured):
        from validator import OntologyValidator
        v = OntologyValidator()
    return v


@st.cache_resource
def get_extractor():
    captured = io.StringIO()
    with contextlib.redirect_stdout(captured):
        from extractor import TripleExtractor
        e = TripleExtractor()
    return e


def get_ground_truth() -> dict:
    gt_path = Path("contract_ground_truth.json")
    if gt_path.exists():
        with open(gt_path, "r") as f:
            return json.load(f)
    return {}


def list_contracts() -> list:
    data_dir = Path("data")
    if not data_dir.exists():
        return []
    return [p.stem.replace("Contract_", "") for p in sorted(data_dir.glob("Contract_*.pdf"))]


# ===================================================================
# PAGE 1: OV-RAG Demo
# ===================================================================
def page_demo():
    st.title("OV-RAG Demo")
    st.markdown("""
    Dieses Tool demonstriert den **Ontology-Validated RAG (OV-RAG)** Ansatz aus meiner Bachelorarbeit.
    Er erkennt logische Widersprüche in LLM-generierten Antworten über Kreditverträge,
    indem er die Antworten gegen eine formale Ontologie (FIBO/LOAN) prüft.
    """)

    # --- How it works ---
    with st.expander("Wie funktioniert OV-RAG?", expanded=False):
        st.markdown("""
        Der OV-RAG-Prototyp besteht aus **drei Komponenten**, die nacheinander ausgeführt werden:

        **Schritt 1 — RAG Generator (Component A)**
        > Ein Retrieval-Augmented Generation System. Das PDF wird in Textabschnitte zerlegt,
        > in einer Vektordatenbank (ChromaDB) gespeichert, und per Ähnlichkeitssuche werden
        > die relevantesten Abschnitte zur Beantwortung der Frage an GPT-4o übergeben.

        **Schritt 2 — Triple Extractor (Component B)**
        > Die generierte Antwort wird von GPT-4o in **strukturierte Tripel** (Subjekt, Prädikat, Objekt)
        > umgewandelt und auf LOAN-Ontologie-Klassen gemappt.
        > z.B.: `(John Smith, rdf:type, NaturalPerson)` oder `(Loan_001, hasCollateral, Property_A)`

        **Schritt 3 — Ontology Validator (Component C)**
        > Die Tripel werden in eine temporäre OWL-Ontologie eingefügt und der **Pellet-Reasoner**
        > prüft auf logische Konsistenz. Wenn ein Widerspruch erkannt wird (z.B. eine Mortgage
        > die gleichzeitig "unsecured" ist), wird die Antwort als **inkonsistent** markiert.

        **Correction Loop**
        > Bei einem Widerspruch wird die Antwort bis zu 3x mit dem Validierungs-Feedback
        > an GPT-4o zurückgegeben. Wenn die Korrektur scheitert → **Hard-Reject**.
        """)

    if not os.getenv("OPENAI_API_KEY"):
        st.error("OPENAI_API_KEY nicht gesetzt. Bitte in `.env` Datei eintragen.")
        return

    st.divider()

    # --- Input ---
    st.subheader("1. Vertrag auswählen")

    source_mode = st.radio("PDF-Quelle:", ["Vorhandener Vertrag", "Eigenes PDF hochladen"], horizontal=True)

    pdf_path = None
    if source_mode == "Vorhandener Vertrag":
        contracts = list_contracts()
        if not contracts:
            st.warning("Keine Verträge gefunden. Bitte zuerst `python generate_test_pdfs.py` ausführen.")
            return
        gt = get_ground_truth()

        # Build display options
        options = []
        for cid in contracts:
            info = gt.get(cid, {})
            label = info.get("label", "")
            ctype = info.get("clash_type") or ""
            display = f"Contract {cid}"
            if label == "CLEAN":
                display += "  —  Clean (kein Widerspruch)"
            elif label == "CLASH":
                type_names = {
                    "secured_unsecured": "Secured vs Unsecured",
                    "openend_closedend": "OpenEnd vs ClosedEnd",
                    "borrower_type": "Falscher Borrower-Typ",
                    "lender_type": "Falscher Lender-Typ",
                }
                display += f"  —  CLASH: {type_names.get(ctype, ctype)}"
            options.append((cid, display))

        selected_display = st.selectbox(
            "Vertrag auswählen:",
            [d for _, d in options],
            help="Contracts 001-060 sind korrekt, 061-100 enthalten verschiedene logische Widersprüche.",
        )
        cid = options[[d for _, d in options].index(selected_display)][0]
        pdf_path = f"data/Contract_{cid}.pdf"

        # Show ground truth info
        info = gt.get(cid, {})
        if info.get("clash_description"):
            st.caption(f"Ground Truth: {info['clash_description']}")

    else:
        uploaded = st.file_uploader("PDF hochladen:", type=["pdf"])
        if uploaded:
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
            tmp.write(uploaded.read())
            tmp.close()
            pdf_path = tmp.name

    st.subheader("2. Frage stellen")

    example_questions = {
        "(Eigene Frage eingeben)": "",
        "Welcher Kredittyp?": "What type of loan is described in this document? Is it a consumer loan, commercial loan, mortgage, student loan, or another type?",
        "Wer ist Borrower/Lender?": "Who is the borrower and who is the lender of this loan? Are they individuals or organizations?",
        "Secured oder Unsecured?": "Is this loan secured or unsecured? If secured, what collateral is specified?",
        "Revolving oder Fixed-term?": "Is this a revolving (open-end) credit facility or a fixed-term (closed-end) loan? What are the repayment terms?",
        "Zusammenfassung aller Konditionen": "Summarize the key financial terms: principal amount, interest rate, loan type, parties involved, and whether the loan is secured.",
    }

    selected_example = st.selectbox("Beispiel-Frage auswählen:", list(example_questions.keys()))

    if selected_example == "(Eigene Frage eingeben)":
        question = st.text_input("Frage:", placeholder="z.B. Is this loan secured or unsecured?")
    else:
        question = st.text_input("Frage:", value=example_questions[selected_example])

    st.subheader("3. Modus wählen")
    col_mode1, col_mode2 = st.columns(2)
    with col_mode1:
        validate = st.toggle("OV-RAG Validierung aktivieren", value=True)
    with col_mode2:
        if validate:
            st.caption("Antwort wird gegen LOAN-Ontologie geprüft (mit Correction Loop)")
        else:
            st.caption("Plain RAG — Antwort ohne Ontologie-Prüfung")

    st.divider()

    # --- Run ---
    can_run = pdf_path and question and len(question.strip()) > 0
    if st.button("Abfrage starten", type="primary", disabled=not can_run):
        _run_demo_query(pdf_path, question, validate)

    # --- Display stored result ---
    if "demo_result" in st.session_state:
        _display_demo_result(st.session_state["demo_result"], st.session_state.get("demo_log", ""))


def _run_demo_query(pdf_path: str, question: str, validate: bool):
    """Execute the query and show step-by-step progress."""
    from main import OVRAGSystem
    from rag_pipeline import RAGPipeline

    validator = get_validator()
    extractor = get_extractor()

    system = OVRAGSystem.__new__(OVRAGSystem)
    system.api_key = os.getenv("OPENAI_API_KEY")
    system.rag = RAGPipeline(api_key=system.api_key)
    system.extractor = extractor
    system.validator = validator

    progress = st.empty()
    with progress.container():
        step1 = st.status("Schritt 1: PDF laden & RAG-Antwort generieren...", expanded=True)

    captured = io.StringIO()
    with contextlib.redirect_stdout(captured):
        system.load_documents([pdf_path])

    with progress.container():
        step1.update(label="Schritt 1: PDF geladen, generiere Antwort...", state="running")

    with contextlib.redirect_stdout(captured):
        result = system.process_query(question, validate=validate)

    with progress.container():
        step1.update(label="Schritt 1: RAG-Antwort generiert", state="complete")

    st.session_state["demo_result"] = result
    st.session_state["demo_log"] = captured.getvalue()


def _display_demo_result(result: dict, log: str):
    """Display the query result with explanations."""

    # --- Overall Status ---
    st.subheader("Ergebnis")

    validation = result.get("validation")
    hard_reject = result.get("hard_reject", False)
    accepted_at = result.get("accepted_at_attempt")

    if hard_reject:
        st.error("HARD-REJECT: Die Antwort enthält logische Widersprüche, die auch nach 3 Korrekturen nicht behoben werden konnten. Die Antwort wird abgelehnt.")
    elif validation is None:
        st.info("Plain RAG Modus — keine Ontologie-Validierung durchgeführt.")
    elif validation.is_valid:
        if accepted_at == 0 or accepted_at is None:
            st.success("VALID: Die Antwort ist logisch konsistent mit der LOAN-Ontologie (erster Versuch).")
        else:
            st.success(f"VALID: Die Antwort wurde nach {accepted_at} Korrektur(en) als konsistent akzeptiert.")
    else:
        st.error("INVALID: Die Antwort enthält logische Widersprüche laut LOAN-Ontologie.")

    # --- Answer ---
    st.markdown("#### Generierte Antwort")
    st.markdown(result.get("answer", "*Keine Antwort generiert.*"))

    st.divider()

    # --- Pipeline Steps ---
    col_left, col_right = st.columns(2)

    with col_left:
        st.markdown("#### Extrahierte Tripel")
        st.caption("Component B (Triple Extractor) wandelt die Antwort in strukturierte Fakten um, die gegen die Ontologie geprüft werden können.")
        triples = result.get("triples", [])
        if triples:
            df = pd.DataFrame(triples)
            display_cols = [c for c in ["sub", "sub_type", "pred", "obj", "obj_type"] if c in df.columns]
            if display_cols:
                df_display = df[display_cols].rename(columns={
                    "sub": "Subjekt", "sub_type": "Typ (S)",
                    "pred": "Prädikat",
                    "obj": "Objekt", "obj_type": "Typ (O)",
                })
                st.dataframe(df_display, use_container_width=True, hide_index=True)
            else:
                st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.caption("Keine Tripel extrahiert — die Antwort enthielt keine ontologie-relevanten Aussagen.")

    with col_right:
        st.markdown("#### Validierungs-Ergebnis")
        st.caption("Component C (Ontology Validator) fügt die Tripel in eine OWL-Ontologie ein und lässt den Pellet-Reasoner auf logische Konsistenz prüfen.")
        if validation:
            st.code(validation.explanation, language=None)
        elif hard_reject:
            st.warning(result.get("hard_reject_reason", ""))
        else:
            st.caption("Keine Validierung durchgeführt (Plain RAG Modus).")

    # --- Correction Loop ---
    attempts = result.get("correction_attempts", [])
    if len(attempts) > 1:
        st.divider()
        st.markdown("#### Correction Loop")
        st.caption(
            "Wenn die Validierung fehlschlägt, wird die Antwort mit dem Fehler-Feedback "
            "an GPT-4o zurückgegeben. Das LLM versucht, die logischen Fehler zu korrigieren. "
            f"Maximal {len(attempts)-1} Korrekturversuch(e) werden durchgeführt."
        )

        for a in attempts:
            num = a["attempt_number"]
            label = "Initialer Versuch" if num == 0 else f"Korrektur #{num}"
            passed = a["is_valid"]
            icon = "✓" if passed else "✗"
            state = "PASS" if passed else "FAIL"

            with st.expander(f"{icon} {label} — {state}"):
                st.markdown(f"**Antwort (gekürzt):** {a['answer'][:400]}{'...' if len(a['answer']) > 400 else ''}")
                if a.get("triples"):
                    st.caption(f"{len(a['triples'])} Tripel extrahiert")
                st.caption(f"**Validierung:** {a.get('explanation', '')[:300]}")

    # --- Source Chunks ---
    sources = result.get("sources", [])
    if sources:
        with st.expander(f"Quell-Textabschnitte aus dem PDF ({len(sources)} Chunks)"):
            st.caption("Diese Textabschnitte wurden per Vektorsuche aus dem PDF geholt und als Kontext an GPT-4o übergeben.")
            for i, doc in enumerate(sources):
                content = doc.page_content if hasattr(doc, "page_content") else str(doc)
                st.text_area(f"Chunk {i+1}", value=content[:600], height=80, disabled=True, key=f"src_{i}_{time.time()}")

    # --- Pipeline Log ---
    if log:
        with st.expander("Komplettes Pipeline-Log (technisch)"):
            st.code(log[-4000:], language=None)


# ===================================================================
# PAGE 2: Batch Evaluation
# ===================================================================
def page_batch():
    st.title("Batch Evaluation")
    st.markdown("""
    Führt die Evaluation über **mehrere Verträge und Fragen** durch.
    Vergleicht OV-RAG (mit Ontologie-Validierung) gegen Plain RAG (ohne).
    Die Ergebnisse werden automatisch gespeichert und können im Dashboard analysiert werden.
    """)

    with st.expander("Was wird gemessen?"):
        st.markdown("""
        - **Jeder Vertrag** wird mit **5 verschiedenen Fragen** abgefragt
        - **Zwei Bedingungen**: OV-RAG (mit Validierung) und Plain RAG (ohne)
        - **Ground Truth**: Verträge 001-060 sind korrekt, 061-100 enthalten Widersprüche
        - **Metriken**: Precision, Recall, F1 (wie gut werden die Widersprüche erkannt?)
        """)

    if not os.getenv("OPENAI_API_KEY"):
        st.error("OPENAI_API_KEY nicht gesetzt.")
        return

    contracts = list_contracts()
    if not contracts:
        st.warning("Keine Verträge gefunden. Bitte `python generate_test_pdfs.py` ausführen.")
        return

    st.divider()

    # --- Config ---
    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("**Verträge**")
        all_contracts = st.checkbox("Alle 100 Verträge", value=False)
        if all_contracts:
            selected_contracts = contracts
        else:
            # Preset selections
            preset = st.selectbox("Vorauswahl:", [
                "Manuell wählen",
                "Schnelltest (5 Verträge)",
                "Clean + je 1 Clash-Typ (8 Verträge)",
            ])
            if preset == "Schnelltest (5 Verträge)":
                selected_contracts = ["001", "030", "061", "076", "096"]
            elif preset == "Clean + je 1 Clash-Typ (8 Verträge)":
                selected_contracts = ["001", "010", "030", "050", "061", "076", "091", "096"]
            else:
                selected_contracts = st.multiselect("Verträge auswählen:", contracts, default=["001", "061"])

    with col2:
        st.markdown("**Fragen**")
        from evaluate import QUESTIONS
        all_questions = st.checkbox("Alle 5 Fragen", value=True)
        if all_questions:
            selected_qids = [q["id"] for q in QUESTIONS]
        else:
            q_options = {f"{q['id']}: {q['target']}": q["id"] for q in QUESTIONS}
            selected_qs = st.multiselect("Fragen:", list(q_options.keys()), default=list(q_options.keys())[:2])
            selected_qids = [q_options[q] for q in selected_qs]

    with col3:
        st.markdown("**Bedingungen**")
        cond_ovrag = st.checkbox("OV-RAG (mit Validierung)", value=True)
        cond_plain = st.checkbox("Plain RAG (ohne Validierung)", value=True)
        conditions = []
        if cond_ovrag:
            conditions.append("ovrag")
        if cond_plain:
            conditions.append("plain")

    if not conditions or not selected_contracts or not selected_qids:
        st.warning("Bitte mindestens 1 Vertrag, 1 Frage und 1 Bedingung auswählen.")
        return

    total = len(selected_contracts) * len(selected_qids) * len(conditions)

    st.divider()
    st.markdown(f"**Geplant: {total} Queries** ({len(selected_contracts)} Verträge × {len(selected_qids)} Fragen × {len(conditions)} Bedingungen)")

    col_run, col_resume = st.columns([1, 1])
    with col_run:
        start = st.button("Evaluation starten", type="primary")
    with col_resume:
        resume = st.checkbox("Bereits erledigte überspringen (Resume)")

    if start:
        from evaluate import EvaluationRunner

        progress_bar = st.progress(0, text="Initialisiere Pipeline...")
        log_container = st.empty()

        runner = EvaluationRunner(
            contracts=selected_contracts,
            questions=selected_qids,
            conditions=conditions,
            resume=resume,
        )

        live_log = []

        def on_progress(completed, total_q, row):
            pct = completed / total_q
            cid = row.get("contract_id", "?")
            cond = row.get("condition", "?").upper()
            qid = row.get("question_id", "?")
            vp = row.get("validation_passed")
            err = row.get("error")

            if err:
                icon = "✗ ERROR"
            elif vp is True:
                icon = "✓ PASS"
            elif vp is False:
                icon = "✗ FAIL"
            else:
                icon = "— N/A"

            line = f"[{completed}/{total_q}] {cid} | {cond:5s} | {qid} | {icon}"
            live_log.append(line)
            progress_bar.progress(pct, text=line)
            log_container.code("\n".join(live_log[-15:]), language=None)

        runner.on_progress = on_progress

        captured = io.StringIO()
        with contextlib.redirect_stdout(captured):
            runner.run()

        progress_bar.progress(1.0, text="Fertig!")
        st.success(f"Evaluation abgeschlossen. {len(runner.results)} Queries verarbeitet.")
        st.balloons()

        st.session_state["batch_done"] = True

    # Link to dashboard
    if st.session_state.get("batch_done") or Path("evaluation_output/evaluation_results.json").exists():
        st.divider()
        st.info("Ergebnisse gespeichert in `evaluation_output/`. Wechsle zum **Dashboard** um die Ergebnisse zu visualisieren.")


# ===================================================================
# PAGE 3: Dashboard
# ===================================================================
def page_dashboard():
    st.title("Evaluation Dashboard")
    st.markdown("Visualisierung der Evaluationsergebnisse — wie gut erkennt OV-RAG die logischen Widersprüche?")

    results_path = Path("evaluation_output/evaluation_results.json")
    if not results_path.exists():
        st.warning("Keine Ergebnisse gefunden. Bitte zuerst eine Batch Evaluation durchführen.")
        return

    with open(results_path, "r") as f:
        data = json.load(f)

    metrics = data.get("metrics", {})
    clash_metrics = data.get("clash_type_metrics", {})
    results = data.get("results", [])

    if not results:
        st.warning("Ergebnis-Datei ist leer.")
        return

    df = pd.DataFrame(results)
    meta = data.get("metadata", {})

    # --- Overview ---
    st.caption(
        f"Evaluation vom {meta.get('timestamp', '?')} — "
        f"{meta.get('total_results', '?')} Queries über "
        f"{len(meta.get('contracts', []))} Verträge"
    )

    st.divider()

    # --- Key Metrics ---
    st.subheader("Kern-Metriken (OV-RAG)")
    st.caption("Bezogen auf die OV-RAG-Bedingung: Wie gut werden Widersprüche in den Clash-Verträgen erkannt?")

    def _fmt(v):
        return f"{v:.3f}" if v is not None else "N/A"

    m1, m2, m3 = st.columns(3)
    m1.metric("Precision", _fmt(metrics.get("precision")),
              help="Anteil der korrekt erkannten Clashes an allen als Clash markierten")
    m2.metric("Recall", _fmt(metrics.get("recall")),
              help="Anteil der erkannten Clashes an allen tatsächlichen Clashes")
    m3.metric("F1 Score", _fmt(metrics.get("f1")),
              help="Harmonisches Mittel von Precision und Recall")

    m4, m5, m6 = st.columns(3)
    m4.metric("Correction Success Rate", _fmt(metrics.get("correction_success_rate")),
              help="Wie oft konnte die Korrektur-Schleife einen Widerspruch beheben?")
    m5.metric("Hard-Reject Rate", _fmt(metrics.get("hard_reject_rate")),
              help="Wie oft wurde eine Antwort nach allen Korrekturversuchen abgelehnt?")
    m6.metric("OV-RAG Queries", metrics.get("total_ovrag_queries", 0))

    st.divider()

    # --- Confusion Matrix + Clash Type ---
    col_cm, col_ct = st.columns(2)

    with col_cm:
        st.subheader("Confusion Matrix")
        st.caption(
            "TP = Clash erkannt, TN = Clean korrekt bestanden, "
            "FP = Fehlalarm, FN = Clash übersehen"
        )
        tp = metrics.get("tp", 0)
        fp = metrics.get("fp", 0)
        fn = metrics.get("fn", 0)
        tn = metrics.get("tn", 0)

        fig_cm = go.Figure(data=go.Heatmap(
            z=[[tp, fn], [fp, tn]],
            x=["Erkannt (Clash)", "Nicht erkannt (Clean)"],
            y=["Tatsächlich Clash", "Tatsächlich Clean"],
            text=[[str(tp), str(fn)], [str(fp), str(tn)]],
            texttemplate="%{text}",
            textfont={"size": 22},
            colorscale="RdYlGn_r",
            showscale=False,
        ))
        fig_cm.update_layout(
            height=350, margin=dict(t=20, b=20),
            yaxis=dict(autorange="reversed"),
        )
        st.plotly_chart(fig_cm, use_container_width=True)

    with col_ct:
        st.subheader("Erkennungsrate pro Clash-Typ")
        st.caption("Welche Art von Widersprüchen wird am besten erkannt?")
        if clash_metrics:
            type_names = {
                "clean": "Clean (kein Clash)",
                "secured_unsecured": "Secured vs Unsecured",
                "openend_closedend": "OpenEnd vs ClosedEnd",
                "borrower_type": "Borrower-Typ",
                "lender_type": "Lender-Typ",
            }
            ct_data = []
            for ctype, m in clash_metrics.items():
                if ctype == "clean":
                    continue  # Clean hat keine "detection rate"
                ct_data.append({
                    "Clash-Typ": type_names.get(ctype, ctype),
                    "Erkennungsrate": m.get("detection_rate") or 0,
                    "TP": m.get("tp", 0),
                    "FN": m.get("fn", 0),
                })
            if ct_data:
                ct_df = pd.DataFrame(ct_data)
                fig_ct = px.bar(
                    ct_df, x="Clash-Typ", y="Erkennungsrate",
                    color="Clash-Typ",
                    text_auto=".2f",
                    range_y=[0, 1.05],
                )
                fig_ct.update_layout(height=350, showlegend=False, margin=dict(t=20, b=20))
                st.plotly_chart(fig_ct, use_container_width=True)
        else:
            st.caption("Keine Clash-Typ-Daten vorhanden.")

    st.divider()

    # --- Per Clash-Type Table ---
    if clash_metrics:
        st.subheader("Detailansicht pro Clash-Typ")
        type_names = {
            "clean": "Clean", "secured_unsecured": "Secured vs Unsecured",
            "openend_closedend": "OpenEnd vs ClosedEnd",
            "borrower_type": "Borrower-Typ", "lender_type": "Lender-Typ",
        }
        ct_rows = []
        for ctype in sorted(clash_metrics.keys()):
            m = clash_metrics[ctype]
            ct_rows.append({
                "Typ": type_names.get(ctype, ctype),
                "TP": m.get("tp", 0), "FP": m.get("fp", 0),
                "TN": m.get("tn", 0), "FN": m.get("fn", 0),
                "Gesamt": m.get("total", 0),
                "Precision": _fmt(m.get("precision")),
                "Recall": _fmt(m.get("recall")),
                "F1": _fmt(m.get("f1")),
            })
        st.dataframe(pd.DataFrame(ct_rows), use_container_width=True, hide_index=True)

    st.divider()

    # --- A/B Comparison: OV-RAG vs Plain RAG ---
    ab_comparison = data.get("ab_comparison", [])
    if ab_comparison:
        st.subheader("A/B Vergleich: OV-RAG vs Plain RAG")
        st.caption("Side-by-side Vergleich der wichtigsten Metriken zwischen den beiden Bedingungen.")

        ab_df = pd.DataFrame(ab_comparison).rename(columns={
            "metric": "Metrik", "plain_rag": "Plain RAG",
            "ovrag": "OV-RAG", "difference": "Differenz",
        })
        st.dataframe(ab_df, use_container_width=True, hide_index=True)

        # Bar charts: ROUGE-L and BERTScore side-by-side
        col_ab1, col_ab2 = st.columns(2)

        with col_ab1:
            rouge_ovrag = metrics.get("avg_rouge_l_ovrag")
            rouge_plain = metrics.get("avg_rouge_l_plain")
            bert_ovrag = metrics.get("avg_bertscore_f1_ovrag")
            bert_plain = metrics.get("avg_bertscore_f1_plain")

            if any(v is not None for v in [rouge_ovrag, rouge_plain, bert_ovrag, bert_plain]):
                nlp_bar_data = []
                if rouge_plain is not None:
                    nlp_bar_data.append({"Metrik": "ROUGE-L", "Bedingung": "Plain RAG", "Wert": rouge_plain})
                if rouge_ovrag is not None:
                    nlp_bar_data.append({"Metrik": "ROUGE-L", "Bedingung": "OV-RAG", "Wert": rouge_ovrag})
                if bert_plain is not None:
                    nlp_bar_data.append({"Metrik": "BERTScore-F1", "Bedingung": "Plain RAG", "Wert": bert_plain})
                if bert_ovrag is not None:
                    nlp_bar_data.append({"Metrik": "BERTScore-F1", "Bedingung": "OV-RAG", "Wert": bert_ovrag})

                if nlp_bar_data:
                    fig_nlp = px.bar(
                        pd.DataFrame(nlp_bar_data),
                        x="Metrik", y="Wert", color="Bedingung",
                        barmode="group", text_auto=".3f",
                        title="NLP-Qualitätsmetriken: Plain RAG vs OV-RAG",
                        range_y=[0, 1.05],
                    )
                    fig_nlp.update_layout(height=350, margin=dict(t=40, b=20))
                    st.plotly_chart(fig_nlp, use_container_width=True)

        with col_ab2:
            lat_ovrag = metrics.get("avg_latency_ovrag")
            lat_plain = metrics.get("avg_latency_plain")
            if lat_ovrag is not None or lat_plain is not None:
                lat_data = []
                if lat_plain is not None:
                    lat_data.append({"Bedingung": "Plain RAG", "Latenz (s)": lat_plain})
                if lat_ovrag is not None:
                    lat_data.append({"Bedingung": "OV-RAG", "Latenz (s)": lat_ovrag})
                fig_lat = px.bar(
                    pd.DataFrame(lat_data),
                    x="Bedingung", y="Latenz (s)", color="Bedingung",
                    text_auto=".1f",
                    title="Durchschnittliche Latenz pro Bedingung",
                )
                fig_lat.update_layout(height=350, showlegend=False, margin=dict(t=40, b=20))
                st.plotly_chart(fig_lat, use_container_width=True)

    st.divider()

    # --- NLP Quality Metrics ---
    st.subheader("NLP-Qualitätsmetriken")
    st.caption(
        "Misst, ob die Antwortqualität durch die Ontologie-Validierung leidet. "
        "ROUGE-L misst die textuelle Überlappung, BERTScore die semantische Ähnlichkeit "
        "zwischen generierter Antwort und Ground-Truth-Referenzantwort."
    )

    n1, n2, n3, n4 = st.columns(4)
    n1.metric(
        "ROUGE-L (OV-RAG)", _fmt(metrics.get("avg_rouge_l_ovrag")),
        help="Durchschnittlicher ROUGE-L F-measure für OV-RAG Antworten",
    )
    n2.metric(
        "ROUGE-L (Plain)", _fmt(metrics.get("avg_rouge_l_plain")),
        help="Durchschnittlicher ROUGE-L F-measure für Plain RAG Antworten",
    )
    n3.metric(
        "BERTScore-F1 (OV-RAG)", _fmt(metrics.get("avg_bertscore_f1_ovrag")),
        help="Durchschnittlicher BERTScore F1 für OV-RAG Antworten",
    )
    n4.metric(
        "BERTScore-F1 (Plain)", _fmt(metrics.get("avg_bertscore_f1_plain")),
        help="Durchschnittlicher BERTScore F1 für Plain RAG Antworten",
    )

    st.divider()

    # --- Latency Section ---
    st.subheader("Latenz-Analyse")
    lat_ovrag = metrics.get("avg_latency_ovrag")
    lat_plain = metrics.get("avg_latency_plain")
    overhead_s = metrics.get("latency_overhead_seconds")
    overhead_pct = metrics.get("latency_overhead_percent")

    l1, l2, l3 = st.columns(3)
    l1.metric(
        "Avg Latenz (OV-RAG)",
        f"{lat_ovrag:.1f}s" if lat_ovrag is not None else "N/A",
        help="Durchschnittliche Gesamtzeit pro Query (RAG + Extraktion + Validierung)",
    )
    l2.metric(
        "Avg Latenz (Plain RAG)",
        f"{lat_plain:.1f}s" if lat_plain is not None else "N/A",
        help="Durchschnittliche Gesamtzeit pro Query (nur RAG)",
    )
    l3.metric(
        "Overhead",
        f"+{overhead_s:.1f}s" if overhead_s is not None else "N/A",
        delta=f"{overhead_pct:.1f}%" if overhead_pct is not None else None,
        delta_color="inverse",
        help="Zusätzliche Latenz durch die Ontologie-Prüfung",
    )

    if overhead_s is not None:
        st.info(
            f"Die Ontologie-Prüfung kostet durchschnittlich **{overhead_s:.1f} Sekunden** "
            f"zusätzlich pro Query (**{overhead_pct:.1f}% Overhead** gegenüber Plain RAG)."
        )

    st.divider()

    # --- Per-Contract Table ---
    st.subheader("Ergebnisse pro Vertrag")
    st.caption("Für jeden Vertrag: wie viele der 5 Fragen wurden korrekt validiert?")

    ovrag_df = df[df["condition"] == "ovrag"].copy() if "condition" in df.columns else pd.DataFrame()

    if not ovrag_df.empty and "validation_passed" in ovrag_df.columns:
        gt = get_ground_truth()
        contract_summary = ovrag_df.groupby("contract_id").agg(
            total=("validation_passed", "count"),
            passed=("validation_passed", lambda x: (x == True).sum()),
            failed=("validation_passed", lambda x: (x == False).sum()),
        ).reset_index()

        contract_summary["Ground Truth"] = contract_summary["contract_id"].map(
            lambda c: gt.get(c, {}).get("label", "?")
        )
        contract_summary["Clash-Typ"] = contract_summary["contract_id"].map(
            lambda c: gt.get(c, {}).get("clash_type") or "—"
        )
        contract_summary = contract_summary.rename(columns={
            "contract_id": "Vertrag", "total": "Queries",
            "passed": "Bestanden", "failed": "Fehlgeschlagen",
        })

        st.dataframe(
            contract_summary[["Vertrag", "Ground Truth", "Clash-Typ", "Queries", "Bestanden", "Fehlgeschlagen"]],
            use_container_width=True, height=400, hide_index=True,
        )

    st.divider()

    # --- Downloads ---
    st.subheader("Ergebnisse herunterladen")
    col_d1, col_d2, col_d3, col_d4 = st.columns(4)

    with col_d1:
        st.download_button(
            "JSON (komplett)",
            data=results_path.read_text(),
            file_name="evaluation_results.json",
            mime="application/json",
        )

    with col_d2:
        csv_path = Path("evaluation_output/evaluation_per_query.csv")
        if csv_path.exists():
            st.download_button(
                "CSV (pro Query)",
                data=csv_path.read_text(),
                file_name="evaluation_per_query.csv",
                mime="text/csv",
            )

    with col_d3:
        clash_csv = Path("evaluation_output/evaluation_per_clash_type.csv")
        if clash_csv.exists():
            st.download_button(
                "CSV (pro Clash-Typ)",
                data=clash_csv.read_text(),
                file_name="evaluation_per_clash_type.csv",
                mime="text/csv",
            )

    with col_d4:
        ab_csv = Path("evaluation_output/evaluation_ab_comparison.csv")
        if ab_csv.exists():
            st.download_button(
                "CSV (A/B Vergleich)",
                data=ab_csv.read_text(),
                file_name="evaluation_ab_comparison.csv",
                mime="text/csv",
            )


# ===================================================================
# Sidebar / Navigation
# ===================================================================
st.sidebar.title("OV-RAG")
st.sidebar.caption("Ontology-Validated RAG für Logische Konsistenz von LLMs")
st.sidebar.divider()

PAGES = {
    "Demo": page_demo,
    "Batch Evaluation": page_batch,
    "Dashboard": page_dashboard,
}

page = st.sidebar.radio("Seite:", list(PAGES.keys()))

st.sidebar.divider()
st.sidebar.markdown("""
**Bachelorarbeit**
*Enhancing Logical Consistency of LLMs with Ontology-Grounded RAG*

**Komponenten:**
- A: RAG Generator (GPT-4o + ChromaDB)
- B: Triple Extractor (GPT-4o → OWL)
- C: Ontology Validator (Pellet Reasoner)
""")

PAGES[page]()
