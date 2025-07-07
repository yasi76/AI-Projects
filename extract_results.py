#!/usr/bin/env python3
"""
Extract company names and save results to JSON for analysis
"""

import json
import asyncio
from company_extractor import process_urls

async def main():
    test_urls = [
        'https://www.acalta.de',
        'https://www.actimi.com',
        'https://www.emmora.de',
        'https://www.alfa-ai.com',
        'https://www.apheris.com',
        'https://www.aporize.com/',
        'https://www.arztlena.com/',
        'https://shop.getnutrio.com/',
        'https://www.auta.health/',
        'https://visioncheckout.com/',
        'https://www.avayl.tech/',
        'https://www.avimedical.com/avi-impact',
        'https://de.becureglobal.com/',
        'https://bellehealth.co/de/',
        'https://www.biotx.ai/',
        'https://www.brainjo.de/',
        'https://brea.app/',
        'https://breathment.com/',
        'https://de.caona.eu/',
        'https://www.careanimations.de/',
        'https://sfs-healthcare.com',
        'https://www.climedo.de/',
        'https://www.cliniserve.de/',
        'https://cogthera.de/#erfahren',
        'https://www.comuny.de/',
        'https://curecurve.de/elina-app/',
        'https://www.cynteract.com/de/rehabilitation',
        'https://www.healthmeapp.de/de/',
        'https://deepeye.ai/',
        'https://www.deepmentation.ai/',
        'https://denton-systems.de/',
        'https://www.derma2go.com/',
        'https://www.dianovi.com/',
        'http://dopavision.com/',
        'https://www.dpv-analytics.com/',
        'http://www.ecovery.de/',
        'https://elixionmedical.com/',
        'https://www.empident.de/',
        'https://eye2you.ai/',
        'https://www.fitwhit.de',
        'https://www.floy.com/',
        'https://fyzo.de/assistant/',
        'https://www.gesund.de/app',
        'https://www.glaice.de/',
        'https://gleea.de/',
        'https://www.guidecare.de/',
        'https://www.apodienste.com/',
        'https://www.help-app.de/',
        'https://www.heynanny.com/',
        'https://incontalert.de/',
        'https://home.informme.info/',
        'https://www.kranushealth.com/de/therapien/haeufiger-harndrang',
        'https://www.kranushealth.com/de/therapien/inkontinenz'
    ]

    # Clean URLs (some had incorrect protocols)
    cleaned_urls = []
    for url in test_urls:
        if url.startswith('https:/') and not url.startswith('https://'):
            url = url.replace('https:/', 'https://')
        elif url.startswith('http:/') and not url.startswith('http://'):
            url = url.replace('http:/', 'http://')
        cleaned_urls.append(url)

    results = await process_urls(cleaned_urls)
    
    # Save results to JSON file
    with open('company_extraction_results.json', 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    print(f"Results saved to company_extraction_results.json")
    print(f"Total URLs processed: {len(results)}")
    
    # Summary statistics
    stats = {
        'total': len(results),
        'success': sum(1 for r in results if r['status'] == 'success'),
        'domain_fallback': sum(1 for r in results if r['status'] == 'domain_fallback'),
        'not_found': sum(1 for r in results if r['status'] == 'not_found'),
        'unreachable': sum(1 for r in results if r['status'] == 'unreachable'),
        'error': sum(1 for r in results if r['status'] == 'error')
    }
    
    print("\nSummary:")
    for status, count in stats.items():
        if status != 'total':
            percentage = (count / stats['total']) * 100
            print(f"{status.title().replace('_', ' ')}: {count} ({percentage:.1f}%)")

if __name__ == "__main__":
    asyncio.run(main())