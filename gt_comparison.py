#!/usr/bin/env python3
"""
Compare extraction results with ground truth company names
"""

import json
import re
from difflib import SequenceMatcher

# Ground truth company names
GT_COMPANIES = [
    "Acalta GmbH",
    "Actimi GmbH", 
    "Actimi GmbH",  # duplicate
    "Ahorn AG",
    "ALFA AI GmbH",
    "apheris AI GmbH",
    "Aporize",
    "Artificy GmbH",
    "Aura Health Technologies GmbH",
    "Aurora Life Sciene GmbH",  # note: typo in GT "Sciene" vs "Science"
    "Auta Health UG",
    "auvisus GmbH",
    "AVAYL GmbH",
    "Avi Medical Operations GmbH",
    "BECURE GmbH",
    "Belle Health GmbH",
    "biotx.ai GmbH",
    "brainjo GmbH",
    "Brea Health GmbH",
    "Breathment GmbH",
    "Caona Health GmbH",
    "CAREANIMATIONS GmbH",
    "Change IT Solutions GmbH",
    "Climedo Health GmbH",
    "Clinicserve GmbH",
    "Cogthera GmbH",
    "comuny GmbH",
    "CureCurve Medical AI GmbH",
    "Cynteract GmbH",
    "Declareme GmbH",
    "deepeye medical GmbH",
    "deepmentation UG",
    "Denton Systems GmbH",
    "derma2go Deutschland GmbH",
    "dianovi GmbH (ehem. MySympto)",
    "docport GmbH",
    "Dopavision GmbH",
    "dpv-analytics GmbH",
    "eCovery GmbH",
    "Elixion Medical",
    "Empident GmbH",
    "eye2you",
    "FitwHit & LABOR FÜR BIOMECHANIK der JLU-Gießen",
    "Floy GmbH",
    "fyzo GmbH",
    "fyzo GmbH",  # duplicate
    "gesund.de GmbH & Co. KG",
    "GLACIE Health UG",
    "Gleea Educational Software GmbH",
    "GuideCare GmbH",
    "Healthy Codes GmbH",
    "Help Mee Schmerztherapie GmbH",
    "iATROS GmbH",
    "heynannyly GmbH",
    "inContAlert GmbH",
    "InformMe GmbH",
    "Kranus Health GmbH",
    "Kranus Health GmbH",  # duplicate
    "Ligari GmbH",
    "Lime Medical GmbH",
    "Limedix GmbH",
    "Lipocheck GmbH",
    "LunaLab GmbH",
    "Medical Intelligence Lab GmbH",
    "MediEm",
    "MeinDoc GmbH",
    "memodio GmbH",
    "mentalis GmbH",
    "MentalStark GmbH",
    "Portabiles HealthCare Technologies GmbH",
    "Prof. Valmed - validated medical Information GmbH",
    "Teleclinic GmbH",
    "PYRA MEDI GmbH",
    "Quantum Diamonds GmbH",
    "Reco-med cloud GmbH",
    "Saas Systems GmbH",
    "Simpleprax UG",
    "Skinuvita GmbH",
    "soventec GmbH",
    "ucura Deutschland GmbH (DeinePflege)",
    "UniteLabs GmbH",
    "MindDoc Health GmbH"
]

# URL to GT mapping (manual mapping based on domain names)
URL_TO_GT = {
    "https://www.acalta.de": "Acalta GmbH",
    "https://www.actimi.com": "Actimi GmbH",
    "https://www.emmora.de": "Declareme GmbH",  # based on domain analysis
    "https://www.alfa-ai.com": "ALFA AI GmbH",
    "https://www.apheris.com": "apheris AI GmbH",
    "https://www.aporize.com/": "Aporize",
    "https://www.arztlena.com/": "iATROS GmbH",  # based on domain analysis
    "https://shop.getnutrio.com/": "Aurora Life Sciene GmbH",
    "https://www.auta.health/": "Auta Health UG",
    "https://visioncheckout.com/": "auvisus GmbH",
    "https://www.avayl.tech/": "AVAYL GmbH",
    "https://www.avimedical.com/avi-impact": "Avi Medical Operations GmbH",
    "https://de.becureglobal.com/": "BECURE GmbH",
    "https://bellehealth.co/de/": "Belle Health GmbH",
    "https://www.biotx.ai/": "biotx.ai GmbH",
    "https://www.brainjo.de/": "brainjo GmbH",
    "https://brea.app/": "Brea Health GmbH",
    "https://breathment.com/": "Breathment GmbH",
    "https://de.caona.eu/": "Caona Health GmbH",
    "https://www.careanimations.de/": "CAREANIMATIONS GmbH",
    "https://sfs-healthcare.com": "Change IT Solutions GmbH",  # based on analysis
    "https://www.climedo.de/": "Climedo Health GmbH",
    "https://www.cliniserve.de/": "Clinicserve GmbH",
    "https://cogthera.de/#erfahren": "Cogthera GmbH",
    "https://www.comuny.de/": "comuny GmbH",
    "https://curecurve.de/elina-app/": "CureCurve Medical AI GmbH",
    "https://www.cynteract.com/de/rehabilitation": "Cynteract GmbH",
    "https://www.healthmeapp.de/de/": "Help Mee Schmerztherapie GmbH",  # based on analysis
    "https://deepeye.ai/": "deepeye medical GmbH",
    "https://www.deepmentation.ai/": "deepmentation UG",
    "https://denton-systems.de/": "Denton Systems GmbH",
    "https://www.derma2go.com/": "derma2go Deutschland GmbH",
    "https://www.dianovi.com/": "dianovi GmbH (ehem. MySympto)",
    "http://dopavision.com/": "Dopavision GmbH",
    "https://www.dpv-analytics.com/": "dpv-analytics GmbH",
    "http://www.ecovery.de/": "eCovery GmbH",
    "https://elixionmedical.com/": "Elixion Medical",
    "https://www.empident.de/": "Empident GmbH",
    "https://eye2you.ai/": "eye2you",
    "https://www.fitwhit.de": "FitwHit & LABOR FÜR BIOMECHANIK der JLU-Gießen",
    "https://www.floy.com/": "Floy GmbH",
    "https://fyzo.de/assistant/": "fyzo GmbH",
    "https://www.gesund.de/app": "gesund.de GmbH & Co. KG",
    "https://www.glaice.de/": "GLACIE Health UG",
    "https://gleea.de/": "Gleea Educational Software GmbH",
    "https://www.guidecare.de/": "GuideCare GmbH",
    "https://www.apodienste.com/": "Healthy Codes GmbH",
    "https://www.help-app.de/": "Help Mee Schmerztherapie GmbH",
    "https://www.heynanny.com/": "heynannyly GmbH",
    "https://incontalert.de/": "inContAlert GmbH",
    "https://home.informme.info/": "InformMe GmbH",
    "https://www.kranushealth.com/de/therapien/haeufiger-harndrang": "Kranus Health GmbH",
    "https://www.kranushealth.com/de/therapien/inkontinenz": "Kranus Health GmbH"
}

def normalize_company_name(name):
    """Normalize company name for comparison"""
    if not name:
        return ""
    # Remove extra punctuation and normalize spacing
    name = re.sub(r'[^\w\s&.-]', '', name)
    name = re.sub(r'\s+', ' ', name).strip()
    return name.lower()

def similarity_score(a, b):
    """Calculate similarity between two strings"""
    return SequenceMatcher(None, normalize_company_name(a), normalize_company_name(b)).ratio()

def main():
    # Load extraction results
    with open('company_extraction_results.json', 'r', encoding='utf-8') as f:
        results = json.load(f)
    
    print("=== COMPANY NAME EXTRACTION ACCURACY ANALYSIS ===\n")
    
    # Statistics
    total_urls = len(results)
    correct_exact = 0
    correct_similar = 0  # similarity > 0.8
    incorrect = 0
    missing_gt = 0
    
    comparison_results = []
    
    for result in results:
        url = result['url']
        extracted = result.get('company', '')
        status = result['status']
        
        if url in URL_TO_GT:
            gt_company = URL_TO_GT[url]
            
            if status == 'success':
                # Calculate similarity
                sim_score = similarity_score(extracted, gt_company)
                
                comparison_results.append({
                    'url': url,
                    'gt': gt_company,
                    'extracted': extracted,
                    'similarity': sim_score,
                    'status': status
                })
                
                if sim_score > 0.95:  # Very similar (accounting for minor differences)
                    correct_exact += 1
                elif sim_score > 0.8:  # Reasonably similar
                    correct_similar += 1
                else:
                    incorrect += 1
            else:
                comparison_results.append({
                    'url': url,
                    'gt': gt_company,
                    'extracted': f"FAILED ({status})",
                    'similarity': 0.0,
                    'status': status
                })
                incorrect += 1
        else:
            missing_gt += 1
            comparison_results.append({
                'url': url,
                'gt': "NOT IN GT LIST",
                'extracted': extracted if status == 'success' else f"FAILED ({status})",
                'similarity': 0.0,
                'status': status
            })
    
    # Sort by similarity score (highest first)
    comparison_results.sort(key=lambda x: x['similarity'], reverse=True)
    
    print("=== EXACT/NEAR-EXACT MATCHES (Similarity > 0.95) ===")
    for result in comparison_results:
        if result['similarity'] > 0.95:
            print(f"✅ {result['gt']}")
            print(f"   Extracted: {result['extracted']}")
            print(f"   URL: {result['url']}")
            print(f"   Similarity: {result['similarity']:.3f}\n")
    
    print("\n=== GOOD MATCHES (Similarity 0.8-0.95) ===")
    for result in comparison_results:
        if 0.8 < result['similarity'] <= 0.95:
            print(f"🟡 {result['gt']}")
            print(f"   Extracted: {result['extracted']}")
            print(f"   URL: {result['url']}")
            print(f"   Similarity: {result['similarity']:.3f}\n")
    
    print("\n=== POOR/INCORRECT MATCHES (Similarity < 0.8) ===")
    for result in comparison_results:
        if result['similarity'] <= 0.8 and result['gt'] != "NOT IN GT LIST":
            print(f"❌ {result['gt']}")
            print(f"   Extracted: {result['extracted']}")
            print(f"   URL: {result['url']}")
            print(f"   Similarity: {result['similarity']:.3f}\n")
    
    print("\n=== SUMMARY STATISTICS ===")
    total_with_gt = total_urls - missing_gt
    accuracy_exact = (correct_exact / total_with_gt * 100) if total_with_gt > 0 else 0
    accuracy_similar = ((correct_exact + correct_similar) / total_with_gt * 100) if total_with_gt > 0 else 0
    
    print(f"Total URLs processed: {total_urls}")
    print(f"URLs with GT mapping: {total_with_gt}")
    print(f"URLs not in GT list: {missing_gt}")
    print(f"")
    print(f"Exact matches (>95% similarity): {correct_exact} ({accuracy_exact:.1f}%)")
    print(f"Good matches (>80% similarity): {correct_exact + correct_similar} ({accuracy_similar:.1f}%)")
    print(f"Poor matches (<80% similarity): {incorrect}")
    print(f"")
    print(f"Overall accuracy (exact): {accuracy_exact:.1f}%")
    print(f"Overall accuracy (including similar): {accuracy_similar:.1f}%")

if __name__ == "__main__":
    main()