import { Link, useLocation } from 'react-router-dom'
import './App.css'

function NavBar() {
  const { pathname } = useLocation()

  const links = [
    { label: 'Home', to: '/', active: pathname === '/' },
    { label: 'Historical trends', to: '/history/lot1', active: pathname.startsWith('/history') },
    { label: 'About', to: '/about', active: pathname === '/about' },
  ]

  return (
    <nav className="site-nav" aria-label="Main">
      {links.map((link) => (
        <Link
          key={link.to}
          to={link.to}
          className={`site-nav-link${link.active ? ' active' : ''}`}
          aria-current={link.active ? 'page' : undefined}
        >
          {link.label}
        </Link>
      ))}
    </nav>
  )
}

export default NavBar