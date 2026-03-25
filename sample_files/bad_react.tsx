// Sample React/TypeScript file with intentional violations
import React, { Component } from 'react';

const API_KEY = "sk-abc123xyz456789secret";   // COM001 + JS004: hardcoded secret

// REACT001: Class component instead of functional
class UserCard extends Component {
  render() {
    const user: any = this.props.user;   // TS001: 'any' type
    console.log("Rendering user", user); // JS001: console.log

    return (
      <div style={{ padding: 16, margin: 8 }}>  {/* REACT003: inline styles */}
        <a href="/profile">View Profile</a>      {/* REACT002: raw <a> tag */}
        <img src="/avatar.png" alt="avatar" />  {/* NEXT002: raw <img> */}
      </div>
    );
  }
}

// REACT004: JWT in localStorage
function login(token: string) {
  localStorage.setItem('token', token);

  // REACT005 style — navigating with hardcoded route
  window.location.href = '/dashboard';
}

export default UserCard;
