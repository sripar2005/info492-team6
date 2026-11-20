# Walks all four sample guides and the real-project start in a fresh browser. Needs the site served at :8765
# (python3 -m http.server 8765) and Playwright with Chrome. python3 tools/guide_test.py
import sys, re
from playwright.sync_api import sync_playwright
BASE='http://localhost:8765'
errs=[]
def panel(pg):
    pg.wait_for_timeout(900)
    el=pg.query_selector('#guide')
    if not el or not el.is_visible(): return '(no panel)'
    return re.sub(r'\s+',' ',el.inner_text())[:160]
def step(pg,label): print('  ',label,'->',panel(pg))
def begin(b, role, w=1280, h=900):
    ctx=b.new_context(viewport={'width':w,'height':h}); pg=ctx.new_page(); pg.on('pageerror',lambda e: errs.append(role+': '+str(e)))
    pg.goto(BASE+'/app/'); pg.wait_for_timeout(1500)
    assert 'Choose your role' in pg.inner_text('#app'), pg.inner_text('#app')[:200]
    pg.click('[data-gsrole="%s"]'%role); pg.wait_for_timeout(7000)
    return pg
def modal_btn(pg,text):
    pg.locator('.modal [data-mb]',has_text=text).first.click(); pg.wait_for_timeout(1500)
with sync_playwright() as p:
    b=p.chromium.launch(executable_path='/usr/bin/google-chrome')
    print('GC'); pg=begin(b,'gc'); step(pg,'start')
    pg.click('#guide [data-gd="ack"]'); step(pg,'ack')
    pg.locator('.g-target').first.click(); pg.wait_for_timeout(1500); step(pg,'opened')
    pg.click('[data-tbundleall]'); pg.wait_for_timeout(1500); step(pg,'bundled')
    pg.click('[data-tdraft]'); pg.wait_for_timeout(3000); modal_btn(pg,'Accept'); step(pg,'drafted')
    pg.click('[data-tconfirm]'); pg.wait_for_timeout(1200); modal_btn(pg,'Confirm'); step(pg,'confirmed')
    pg.click('[data-tcheck]'); pg.wait_for_timeout(1800); step(pg,'checked')
    pg.fill('#texplain','Will remove the fee on NSS items.'); pg.click('[data-texplain]'); pg.wait_for_timeout(1800); step(pg,'explained')
    pg.click('[data-tact="submit"]'); pg.wait_for_timeout(1800); step(pg,'sent')
    arch=pg.evaluate("[...document.querySelectorAll('#viewas option')].find(o=>/Architecture/.test(o.text)).value"); pg.select_option('#viewas',arch); pg.wait_for_timeout(2000); step(pg,'switched')
    pg.screenshot(path='/tmp/shots/g_gc_done.png')
    print('SUB'); pg=begin(b,'sub'); step(pg,'start'); pg.screenshot(path='/tmp/shots/g_sub_start.png')
    pg.click('#guide [data-gd="ack"]'); step(pg,'ack')
    pg.locator('[data-fconfirm]').first.click(); pg.wait_for_timeout(2000); step(pg,'confirmed note')
    pg.click('[data-tact="submit"]'); pg.wait_for_timeout(1800); step(pg,'sent')
    pg.click('#guide [data-gd="go"]') if pg.query_selector('#guide [data-gd="go"]') else None; pg.wait_for_timeout(1200); step(pg,'went')
    pg.click('#guide [data-gd="ack"]'); step(pg,'ack2')
    gc=pg.evaluate("[...document.querySelectorAll('#viewas option')].find(o=>/Example Builders/.test(o.text)).value"); pg.select_option('#viewas',gc); pg.wait_for_timeout(2000); step(pg,'switched')
    print('ARCH'); pg=begin(b,'architect'); step(pg,'start')
    pg.click('#guide [data-gd="ack"]'); step(pg,'ack')
    pg.locator('.g-target').first.click(); pg.wait_for_timeout(1800); step(pg,'opened')
    pg.click('#guide [data-gd="ack"]'); step(pg,'read')
    pg.click('[data-tact="forward"]'); pg.wait_for_timeout(1800); step(pg,'forwarded')
    ow=pg.evaluate("[...document.querySelectorAll('#viewas option')].find(o=>/School District/.test(o.text)).value"); pg.select_option('#viewas',ow); pg.wait_for_timeout(2000); step(pg,'switched')
    print('OWNER'); pg=begin(b,'owner',390,844); step(pg,'start'); pg.screenshot(path='/tmp/shots/g_owner_phone.png')
    pg.click('#guide [data-gd="ack"]'); step(pg,'ack')
    pg.locator('.g-target').first.click(); pg.wait_for_timeout(1800); step(pg,'opened'); pg.screenshot(path='/tmp/shots/g_owner_phone2.png')
    pg.click('#guide [data-gd="ack"]'); step(pg,'inside')
    pg.click('[data-tact="approve"]'); pg.wait_for_timeout(1800); step(pg,'approved')
    pg.click('[data-nav="activity"]'); pg.wait_for_timeout(1800); step(pg,'activity')
    print('REAL'); ctx=b.new_context(viewport={'width':1280,'height':900}); pg=ctx.new_page(); pg.on('pageerror',lambda e: errs.append('real: '+str(e)))
    pg.goto(BASE+'/app/'); pg.wait_for_timeout(1200); pg.fill('#gsmail','test@example.com'); pg.click('#gsemail button'); pg.wait_for_timeout(3000); step(pg,'real start'); pg.screenshot(path='/tmp/shots/g_real.png')
    b.close()
print('ERRORS',errs)
