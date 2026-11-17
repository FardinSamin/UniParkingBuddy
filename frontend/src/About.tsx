import './App.css'

function About() {
  return (
    <div className="about-page">
      <section className="about-hero">
        <div className="about-container">
          <p className="about-eyebrow">About</p>
          <h1 className="about-title">What is UniParkingBuddy?</h1>
          <p className="about-hero-text">
            A live look at campus parking. See which spots are open before you drive in,
            so you spend less time circling the lot and more time getting where you're going.
          </p>
        </div>
      </section>

      <section className="about-section">
        <div className="about-container">
          <h2 className="about-heading">How it works</h2>
          <div className="about-how">
            <p>
              Cameras keep an eye on each lot. Each parking space is checked to see if it is occupied by a car or not. 
              The map and counts update automatically as cars come and go, so you get a current picture of which spots are open.
            </p>
          </div>
        </div>
      </section>

      <section className="about-section about-section-white">
        <div className="about-container">
          <h2 className="about-heading">Reading the lot map</h2>
          <div className="about-legend">
            <div className="about-legend-card">
              <span className="about-swatch about-swatch-open"></span>
              <strong>Green</strong>
              <span>The space is open.</span>
            </div>
            <div className="about-legend-card">
              <span className="about-swatch about-swatch-taken"></span>
              <strong>Red</strong>
              <span>The space is taken.</span>
            </div>
          </div>
          <p className="about-note">
            Tree islands and dividers on the map are for reference only. They aren't
            parking spaces.
          </p>
        </div>
      </section>
      </div>
  )
}

export default About
