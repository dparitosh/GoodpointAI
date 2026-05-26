/**
 * Admin Settings Page
 * 
 * Central administration page for managing all system configurations
 */

import React from 'react';
import AdminConfigManager from '../../components/admin-config-manager/index.jsx';
import '../../components/admin-config-manager.css';

function AdminSettingsPage() {
  return (
    <div className="admin-settings-page">
      <AdminConfigManager />
    </div>
  );
}

export default AdminSettingsPage;
export { AdminSettingsPage };
