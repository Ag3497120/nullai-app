import React, { useState, useEffect } from 'react';
import { fetchDomains as apiFetchDomains, fetchDomain, updateDomain } from '../services/api';
import { useAuth } from '../contexts/AuthContext';

interface Axis {
  name: string;
  description: string;
  keywords: string[];
}

interface Domain {
  domain_id: string;
  name: string;
  description: string;
  axes?: Axis[];
  axis_count?: number;
}

export const DomainEditorPage: React.FC = () => {
  const { user } = useAuth();
  const [domains, setDomains] = useState<Domain[]>([]);
  const [selectedDomain, setSelectedDomain] = useState<Domain | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState('');
  const [successMessage, setSuccessMessage] = useState('');

  useEffect(() => {
    loadDomains();
  }, []);

  const loadDomains = async () => {
    try {
      setError('');
      const data = await apiFetchDomains();
      setDomains((data as any).domains || data);
    } catch (err: any) {
      setError(err.message || 'Failed to load domains');
    } finally {
      setIsLoading(false);
    }
  };

  const loadDomainDetails = async (domainId: string) => {
    try {
      setError('');
      const data = await fetchDomain(domainId);
      setSelectedDomain(data);
    } catch (err: any) {
      setError(err.message || 'Failed to load domain details');
    }
  };

  const handleSave = async () => {
    if (!selectedDomain) return;

    setIsSaving(true);
    setError('');

    try {
      await updateDomain(selectedDomain.domain_id, selectedDomain);
      setSuccessMessage('Domain saved successfully');
      setTimeout(() => setSuccessMessage(''), 3000);
      loadDomains();
    } catch (err: any) {
      setError(err.message || 'Failed to save domain');
    } finally {
      setIsSaving(false);
    }
  };

  const handleAxisChange = (index: number, field: keyof Axis, value: string | string[]) => {
    if (!selectedDomain?.axes) return;

    const updatedAxes = [...selectedDomain.axes];
    updatedAxes[index] = { ...updatedAxes[index], [field]: value };
    setSelectedDomain({ ...selectedDomain, axes: updatedAxes });
  };

  const handleAddAxis = () => {
    if (!selectedDomain) return;

    const newAxis: Axis = {
      name: '',
      description: '',
      keywords: [],
    };

    setSelectedDomain({
      ...selectedDomain,
      axes: [...(selectedDomain.axes || []), newAxis],
    });
  };

  const handleRemoveAxis = (index: number) => {
    if (!selectedDomain?.axes) return;

    const updatedAxes = selectedDomain.axes.filter((_, i) => i !== index);
    setSelectedDomain({ ...selectedDomain, axes: updatedAxes });
  };

  if (isLoading) {
    return <div className="loading">Loading domains...</div>;
  }

  return (
    <div className="domain-editor">
      <h2>Domain Editor</h2>

      {error && <div className="error-message">{error}</div>}
      {successMessage && <div className="success-message">{successMessage}</div>}

      <div className="domain-layout">
        {/* Domain List */}
        <div className="domain-list">
          <h3>Domains</h3>
          {domains.map((domain) => (
            <div
              key={domain.domain_id}
              className={`domain-item ${selectedDomain?.domain_id === domain.domain_id ? 'selected' : ''}`}
              onClick={() => loadDomainDetails(domain.domain_id)}
            >
              <strong>{domain.name}</strong>
              <span className="axis-count">{domain.axis_count} axes</span>
            </div>
          ))}
        </div>

        {/* Domain Editor */}
        <div className="domain-details">
          {selectedDomain ? (
            <>
              <div className="form-group">
                <label>Domain Name</label>
                <input
                  type="text"
                  value={selectedDomain.name}
                  onChange={(e) => setSelectedDomain({ ...selectedDomain, name: e.target.value })}
                />
              </div>

              <div className="form-group">
                <label>Description</label>
                <textarea
                  value={selectedDomain.description}
                  onChange={(e) => setSelectedDomain({ ...selectedDomain, description: e.target.value })}
                  rows={3}
                />
              </div>

              <h3>Axes</h3>
              {selectedDomain.axes?.map((axis, index) => (
                <div key={index} className="axis-card">
                  <div className="axis-header">
                    <input
                      type="text"
                      placeholder="Axis name"
                      value={axis.name}
                      onChange={(e) => handleAxisChange(index, 'name', e.target.value)}
                    />
                    <button
                      className="remove-btn"
                      onClick={() => handleRemoveAxis(index)}
                    >
                      Remove
                    </button>
                  </div>
                  <input
                    type="text"
                    placeholder="Description"
                    value={axis.description}
                    onChange={(e) => handleAxisChange(index, 'description', e.target.value)}
                  />
                  <input
                    type="text"
                    placeholder="Keywords (comma-separated)"
                    value={axis.keywords.join(', ')}
                    onChange={(e) => handleAxisChange(index, 'keywords', e.target.value.split(',').map(k => k.trim()))}
                  />
                </div>
              ))}

              <div className="button-group">
                <button className="add-btn" onClick={handleAddAxis}>
                  + Add Axis
                </button>
                <button
                  className="save-btn"
                  onClick={handleSave}
                  disabled={isSaving}
                >
                  {isSaving ? 'Saving...' : 'Save Domain'}
                </button>
              </div>
            </>
          ) : (
            <p className="select-prompt">Select a domain to edit</p>
          )}
        </div>
      </div>
    </div>
  );
};
