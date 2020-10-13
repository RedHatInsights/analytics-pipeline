const puppeteer = require('puppeteer');

const width = 1920;
const height = 1280;


describe("smoketest", () => {

    let browser = null;
    let ssoPage = null;
    let cloudPage = null;

    beforeAll(async () => {
        console.log('smoketest spinup');

        browser = await puppeteer.launch({
            headless: true,
            ignoreHTTPSErrors: true,
            args: [`--window-size=${width},${height}`]
        });

        // check keycloak landing page ...
        ssoPage = await browser.newPage();
        ssoPage.setViewport({
            width: 1920,
            height: 1080
        });

        let count = 0;
        while (count < 10) {
            try {
                ssoPage.waitForNavigation();
                await ssoPage.goto('https://sso.local.redhat.com:8443');
            } catch {
                //await ssoPage.waitFor(2000);
                console.log(`${count}. sleeping 5s`);
            }
            count = count + 1;
        };
        await ssoPage.screenshot({path: 'screens/1_sso.png'});

        cloudPage = await browser.newPage();
        cloudPage.setViewport({
            width: width,
            height: height
        });
        await cloudPage.goto('https://prod.foo.redhat.com:1337', {"waitUntil" : "networkidle2"});
        await cloudPage.screenshot({path: 'screens/2_cloud_landing.png'});


    });

    afterAll(async () => {
        await browser.close();
        console.log('smoketest teardown');
    });

    it("can be logged in", async () => {
        console.log('starting login');

		// wait for login button to load ...
		await cloudPage.evaluate(async () => {
			const loginButton = document.querySelectorAll("button");
			if (loginButton.complete) {
				return;
			};
		});
		await cloudPage.screenshot({path: 'screens/3_cloud_landing_login_button.png'});

        // click the login button ...
        await cloudPage.$eval('[data-ouia-component-id="1"]', el => el.click());
        await cloudPage.waitFor(1000);
        await cloudPage.screenshot({path: 'screens/4_login_page.png'});

        // supply username
        await cloudPage.type('#username', 'bob');

        // supply password
        await cloudPage.type('#password', 'redhat1234');

        // click login ...
        await cloudPage.$eval('#kc-login', el => el.click());
        await cloudPage.waitFor(1000);
        await cloudPage.screenshot({path: 'screens/5_after_login.png'});


    });

    it("can load the clusters page", async () => {
        console.log('opening clusters/dashboard page ...');
		await cloudPage.$eval('[href="/ansible/automation-analytics"]', el => el.click());
		await cloudPage.waitFor(2000);
		await cloudPage.screenshot({path: 'screens/6_clusters.png'});
    });
});
