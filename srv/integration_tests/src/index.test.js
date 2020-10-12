const puppeteer = require('puppeteer');

const width = 1920;
const height = 1280;

(async () => {
    const browser = await puppeteer.launch({
        headless: true,
        ignoreHTTPSErrors: true,
        args: [`--window-size=${width},${height}`]
    });

    /*
    // check keycloak landing page ...
    const ssoPage = await browser.newPage();
    ssoPage.setViewport({
        width: 1920,
        height: 1080
    });
    await ssoPage.goto('https://sso.local.redhat.com:8443');
    await ssoPage.screenshot({path: 'sso.png'});
    */

    // open cloud ...
    const cloudPage = await browser.newPage();
    cloudPage.setViewport({
        width: width,
        height: height
    });
    await cloudPage.goto('https://prod.foo.redhat.com:1337', {"waitUntil" : "networkidle2"});
    //await cloudPage.waitFor(100000);
    await cloudPage.screenshot({path: 'cloud1.png'});

    // wait for login button to load ...
    await cloudPage.evaluate(async () => {
        const loginButton = document.querySelectorAll("button");
        if (loginButton.complete) {
            return;
        };
    });
    await cloudPage.screenshot({path: 'cloud2.png'});

    // click the login button ...
    await cloudPage.$eval('[data-ouia-component-id="1"]', el => el.click());
    await cloudPage.waitFor(1000);
    await cloudPage.screenshot({path: 'login.png'});

    // supply username
    await cloudPage.type('#username', 'bob');

    // supply password
    await cloudPage.type('#password', 'redhat1234');

    // click login ...
    await cloudPage.$eval('#kc-login', el => el.click());
    await cloudPage.waitFor(1000);

    // open the AA link ...
    await cloudPage.$eval('[href="/ansible/automation-analytics"]', el => el.click());
    await cloudPage.waitFor(2000);
    await cloudPage.screenshot({path: 'aa-clusters.png'});

    // click on each top template to load the modal ..
    const templates = await cloudPage.$$('li[aria-labelledby="top-templates-detail"] > div > a');
    for (let i=0; i<templates.length; i++) {
        console.log(i);
        await templates[i].click();
        await cloudPage.waitFor(1000);
        await cloudPage.screenshot({path: `top-template-${i}.png`});
        await cloudPage.$eval('button[aria-label="Close"]', el => el.click());
    }

    console.log('DONE!!!!!!!!!!!!');
    await cloudPage.waitFor(10000);
    await browser.close();
})();

describe("DO STUFF", () => {
    it("show be cool!", () => {
    });
});
