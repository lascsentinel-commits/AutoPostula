import asyncio
from playwright.async_api import async_playwright

async def inspect():
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp('http://localhost:9222')
        ctx = browser.contexts[0]
        pg = None
        for page in ctx.pages:
            if 'firstjob.me' in page.url:
                pg = page
                break
        if not pg:
            print('No se encontró página firstjob abierta')
            return
        
        print('FirstJob URL:', pg.url)
        info = await pg.evaluate(r'''() => {
            const groups = [];
            const radioNames = new Set();
            document.querySelectorAll('input[type="radio"]').forEach(r => radioNames.add(r.name));
            
            for (let name of radioNames) {
                const inputs = Array.from(document.querySelectorAll('input[name="' + name + '"]'));
                const firstInput = inputs[0];
                const container = firstInput.closest('.form-group') || firstInput.closest('div[class*="question"]') || firstInput.closest('fieldset') || firstInput.parentElement.parentElement;
                let qText = '';
                if (container) {
                    const qEl = container.querySelector('p, label:not(.cb-container), h4, h5, .title');
                    if (qEl) qText = qEl.innerText.trim();
                    else qText = container.innerText.trim();
                }
                const options = inputs.map(inp => {
                    const lbl = inp.closest('label') || inp.parentElement;
                    return { val: inp.value, text: lbl ? lbl.innerText.trim() : '' };
                });
                groups.push({ name: name, question: qText, options: options });
            }
            return groups;
        }''')
        for g in info:
            print(f"Pregunta ({g['name']}): {g['question'][:120]}")
            print(f"  Opciones: {g['options']}")
            print()

asyncio.run(inspect())

