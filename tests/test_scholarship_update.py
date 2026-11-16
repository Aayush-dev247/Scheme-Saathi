"""Regressions against downloaded official documents, not invented scheme answers."""
import json
import re
from pathlib import Path
import pytest
from rag import RAG
from scrape import ROOT

@pytest.fixture(scope='module')
def engine():
    e=RAG()
    e.load()
    return e

@pytest.mark.parametrize('question',[
 'BCA students ke liye scholarship kaunsi hai?',
 'BCA girls ke liye scholarship eligibility kya hai?',
 'Which scholarships explicitly include BCA?',
 'बीसीए छात्रों के लिए कौन सी छात्रवृत्ति है?',
])
def test_bca_retrieves_explicit_course_and_restrictions(engine,question):
    sources=engine.retrieve(question)
    assert 1 <= len(sources) <= 4
    assert any(s['source']=='06b61ec2ff17.pdf' and s['page']==11 for s in sources)
    # Gender and income restrictions must be present in retrieved passages.
    assert any('girl candidate' in s['text'].lower() and '8 lakh' in s['text'].lower() for s in sources)
    assert all(s['source']!='b449d35120f0.pdf' for s in sources)
    assert all(-1 <= s['score'] <= 1 for s in sources)

def test_updated_csss_rule_is_retrievable(engine):
    sources=engine.retrieve('PM USP CSSS parental family income ceiling eligibility')
    assert any(s['source']=='0c9e2041dd1b.pdf' and '4.5 lakh' in s['text'] for s in sources)

def test_superseded_pdf_not_in_default_index(engine):
    assert not any(s['source']=='b449d35120f0.pdf' for s in engine.rows)

def test_sarswati_annexure_preserves_physical_pages(engine):
    rows=[s for s in engine.rows if s['source']=='06b61ec2ff17.pdf']
    assert rows and all(s['page'] in [10,11,12,13,14] for s in rows)

def test_no_personal_record_access(engine):
    assert engine.ask('Mera scholarship application status kya hai?')['mode']=='not_found'

def test_no_key_uses_real_excerpts(engine,monkeypatch):
    monkeypatch.delenv('GROQ_API_KEY',raising=False)
    monkeypatch.setenv('LLM_PROVIDER','groq')
    result=engine.ask('BCA students ke liye scholarship kaunsi hai?')
    assert result['mode']=='extractive'
    for i,s in enumerate(result['sources'],1):
        assert s['text'] in result['answer'] and f'[{i}]' in result['answer']
    assert 'unverified_cycle' in result['answer']
