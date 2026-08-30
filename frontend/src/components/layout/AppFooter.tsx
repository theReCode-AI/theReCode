import { Footer, FooterCopyright, FooterLink, FooterLinkGroup } from "flowbite-react";

export function AppFooter() {
  const year = new Date().getFullYear();

  return (
    <Footer
      container
      className="shrink-0 rounded-none border-t border-gray-200 bg-white dark:border-gray-700 dark:bg-gray-800"
    >
      <FooterCopyright href="/dashboard" by="theReCode™" year={year} />
      <FooterLinkGroup>
        <FooterLink href="https://www.linkedin.com/in/md-shariar-kabir/" target="_blank">
          LinkedIn
        </FooterLink>
        <FooterLink href="https://github.com/codezerro" target="_blank">
          GitHub
        </FooterLink>
      </FooterLinkGroup>
    </Footer>
  );
}
