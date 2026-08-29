import { Footer, FooterCopyright, FooterLink, FooterLinkGroup } from "flowbite-react";
import { useNavigate } from "react-router-dom";

function FooterNavLink({ to, label }: { to: string; label: string }) {
  const navigate = useNavigate();

  return (
    <FooterLink
      href={to}
      onClick={(event) => {
        event.preventDefault();
        navigate(to);
      }}
    >
      {label}
    </FooterLink>
  );
}

export function AppFooter() {
  const year = new Date().getFullYear();

  return (
    <Footer container className="shrink-0 rounded-none border-t border-gray-200 bg-white">
      <FooterCopyright href="/dashboard" by="CodeThera™" year={year} />
      <FooterLinkGroup>
        {/* <FooterNavLink to="/dashboard" label="Dashboard" />
        <FooterNavLink to="/projects" label="Projects" />
        <FooterNavLink to="/settings" label="Settings" /> */}
        <FooterLink href="https://www.linkedin.com/in/md-shariar-kabir/" target="_blank">LinkedIn</FooterLink>
        <FooterLink href="https://github.com/codezerro" target="_blank">GitHub</FooterLink>
      </FooterLinkGroup>
    </Footer>
  );
}
