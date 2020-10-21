/*
describe('SSO self-signed cert smoketest', () => {
  it('Visits SSO without cert errors', () => {
    cy.visit('https://sso.local.redhat.com:8443')
  })
})
*/

const baseUrl = 'https://prod.foo.redhat.com:8443';
//const loginUrl = "https://sso.local.redhat.com:8443/auth/realms/redhat-external/protocol/openid-connect/auth?client_id=cloud-services&redirect_uri=https%3A%2F%2Fprod.foo.redhat.com%3A8443%2F&response_mode=fragment&response_type=code&scope=openid"
beforeEach(() => {
    cy.viewport(1280, 1024);
    cy.visit(baseUrl);
    cy.get('[data-ouia-component-id="1"]').click();
    cy.wait(1000);

    //cy.visit(loginUrl)

    cy.get('#username').type('bob');
    cy.get('#password').type('redhat1234');
    cy.get('#kc-login').click();
    cy.wait(1000);
})

describe('automation analytics smoketests', () => {

    xit('can open the crhc landing page', () => {
        cy.visit(baseUrl);
        cy.wait(1000);
    })

    xit('can find and click on the automation-analytics link from the landing page', () => {
        cy.visit(baseUrl);
        const aalink = cy.get('a[href="/ansible/automation-analytics"]').first();
        aalink.click();
        cy.wait(1000);
    })

    xit('has all the AA navigation items', () => {
        cy.visit(baseUrl);
        const aalink = cy.get('a[href="/ansible/automation-analytics"]').first();
        aalink.click();
        cy.wait(1000);

        // pf-c-nav__list
        // li ouiaid=automation-analytics
        const navbar = cy.get('li[ouiaid="automation-analytics"]');
        const navlis = navbar.find('li');
        console.log(navlis);
        navlis.should('have.length', 5)
    })

    it('can open all the AA navigation items', () => {
        cy.visit(baseUrl);
        const aalink = cy.get('a[href="/ansible/automation-analytics"]').first();
        aalink.click();
        cy.wait(1000);

        let navurls = [];

        // pf-c-nav__list
        // li ouiaid=automation-analytics

            /*
            console.log(href[0]);
            console.log(href[0].pathname);

            href[0].click();
            cy.wait(5000);

            cy.location().should((loc) => {
                expect(loc.pathname).to.eq(href[0].pathname);
            })
            */

        cy.get('li[ouiaid="automation-analytics"] > section > ul > li > a').each((href, hid) => {
            console.log('href', hid, href[0].pathname);
            navurls.push(href[0].pathname);
            console.log(navurls);

            /*
            href[0].then((link) => {
                link.click();
                cy.wait(5000);
            });
            */

            /*
            cy.route(href[0].pathname).as('thisurl')
            href[0].click();
            //cy.wait(5000);
            cy.wait(['@thisurl'], { timeout: 15000 }).then(xhr => {
                console.log('xhr', xhr);
            });
            */

            cy.visit(baseUrl + href[0].pathname);
            cy.wait(5000);

        });

        /*
        console.log('navurls', navurls);

        navurls.forEach((url, ix) => {
            console.log(url);
            cy.visit(baseUrl + url);
            cy.wait(5000);

        });

        expect(navurls.length).to.eq(5);
        */

    })

})
