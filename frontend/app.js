document.addEventListener('DOMContentLoaded', () => {
    // =====================================================================
    // Session State
    // =====================================================================
    let currentUser = null;

    // =====================================================================
    // DOM Elements - Auth
    // =====================================================================
    const loginOverlay = document.getElementById('login-overlay');
    const mainApp = document.getElementById('main-app');
    const btnGoogleLogin = document.getElementById('btn-google-login');
    const btnDevBypass = document.getElementById('btn-dev-bypass');
    const loginStatus = document.getElementById('login-status');

    // =====================================================================
    // DOM Elements - App
    // =====================================================================
    const tabBtns = document.querySelectorAll('.tab-btn');
    const tabPanes = document.querySelectorAll('.tab-pane');
    const btnTabDiagnostics = document.getElementById('btn-tab-diagnostics');
    const btnSaveProfile = document.getElementById('btn-save-profile');
    const btnLogout = document.getElementById('btn-logout');
    const userDisplayName = document.getElementById('user-display-name');
    const profileAvatar = document.getElementById('profile-avatar');
    const profileEmail = document.getElementById('profile-email');
    const saveStatus = document.getElementById('save-status');

    const dropZone = document.getElementById('drop-zone');
    const fileInput = document.getElementById('file-input');
    const uploadContent = document.getElementById('upload-content');
    const imagePreview = document.getElementById('image-preview');
    const analyzeBtn = document.getElementById('analyze-btn');
    const terminal = document.getElementById('terminal-log');
    const scanEffect = document.getElementById('scan-effect');
    const radarEffect = document.getElementById('radar-effect');
    
    const loadingDiv = document.getElementById('loading');
    const resultsDiv = document.getElementById('results');
    const resetBtn = document.getElementById('reset-btn');
    
    let currentFile = null;

    // =====================================================================
    // Firebase Google Sign-In
    // =====================================================================
    let googleProvider = null;
    try {
        googleProvider = new firebase.auth.GoogleAuthProvider();
        googleProvider.addScope('email');
        googleProvider.addScope('profile');
    } catch (e) {
        console.warn('Firebase Auth not available:', e.message);
    }

    btnGoogleLogin.addEventListener('click', async () => {
        btnGoogleLogin.disabled = true;
        btnGoogleLogin.querySelector('span').textContent = 'AUTHENTICATING...';
        loginStatus.textContent = '';

        if (!googleProvider) {
            loginStatus.textContent = 'FIREBASE_AUTH_UNAVAILABLE. USE DEV BYPASS.';
            loginStatus.style.color = 'var(--danger)';
            btnGoogleLogin.disabled = false;
            btnGoogleLogin.querySelector('span').textContent = 'SIGN IN WITH GOOGLE';
            return;
        }

        try {
            const result = await firebase.auth().signInWithPopup(googleProvider);
            const user = result.user;
            const email = user.email;
            const name = user.displayName || email.split('@')[0];
            const photoURL = user.photoURL;

            loginStatus.textContent = 'FIREBASE_AUTH_SUCCESS. SYNCING_WITH_SERVER...';
            loginStatus.style.color = 'var(--success)';

            // Sync with our backend
            const response = await fetch('/auth/login', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email, name })
            });
            const data = await response.json();

            if (data.status === 'success') {
                currentUser = { email, name, photoURL, ...data.user };

                // Update header UI
                userDisplayName.textContent = name.toUpperCase();
                if (photoURL) {
                    profileAvatar.src = photoURL;
                    profileAvatar.style.display = 'inline-block';
                }
                profileEmail.textContent = email;

                loginOverlay.classList.remove('active');
                mainApp.style.display = 'block';

                if (data.is_new_user) {
                    // Force new users to fill out their health profile
                    switchTab('tab-profile');
                    addLog('NEW_USER_DETECTED. CONFIGURE_HEALTH_PROFILE.', 'warn');
                } else {
                    // Populate existing profile toggles from DB
                    document.getElementById('is_diabetic').checked = !!currentUser.is_diabetic;
                    document.getElementById('has_high_bp').checked = !!currentUser.has_high_bp;
                    document.getElementById('heart_condition').checked = !!currentUser.heart_condition;
                    document.getElementById('weight_loss_goal').checked = !!currentUser.weight_loss_goal;
                    document.getElementById('is_vegan').checked = !!currentUser.is_vegan;
                    switchTab('tab-scan');
                    addLog(`SESSION_INITIALIZED: ${name} (${email})`, 'success');
                }
            } else {
                loginStatus.textContent = 'SERVER_SYNC_FAILED. TRY_AGAIN.';
                loginStatus.style.color = 'var(--danger)';
            }
        } catch (error) {
            console.error('Login error:', error);
            if (error.code === 'auth/popup-closed-by-user') {
                loginStatus.textContent = 'LOGIN_CANCELLED_BY_USER.';
            } else if (error.code === 'auth/network-request-failed') {
                loginStatus.textContent = 'NETWORK_ERROR. CHECK_CONNECTION.';
            } else if (error.message && error.message.includes('auth/configuration-not-found')) {
                loginStatus.textContent = 'FIREBASE_NOT_CONFIGURED. UPDATE firebase_config.js';
            } else {
                loginStatus.textContent = `AUTH_ERROR: ${error.code || error.message || 'UNKNOWN'}`;
            }
            loginStatus.style.color = 'var(--danger)';
        } finally {
            btnGoogleLogin.disabled = false;
            btnGoogleLogin.querySelector('span').textContent = 'SIGN IN WITH GOOGLE';
        }
    });

    if (btnDevBypass) {
        btnDevBypass.addEventListener('click', async () => {
            btnDevBypass.disabled = true;
            btnDevBypass.querySelector('span').textContent = 'INITIALIZING BYPASS...';
            loginStatus.textContent = 'DEV_BYPASS_INIT. SYNCING_WITH_SERVER...';
            loginStatus.style.color = 'var(--primary)';

            const email = "dev@nutriscan.ai";
            const name = "DEVELOPER";

            try {
                // Sync with our backend
                const response = await fetch('/auth/login', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ email, name })
                });
                const data = await response.json();

                if (data.status === 'success') {
                    currentUser = { email, name, photoURL: null, ...data.user };

                    // Update header UI
                    userDisplayName.textContent = name.toUpperCase();
                    profileEmail.textContent = email;

                    loginOverlay.classList.remove('active');
                    mainApp.style.display = 'block';

                    if (data.is_new_user) {
                        switchTab('tab-profile');
                        addLog('DEV_BYPASS_INIT. CONFIGURE_HEALTH_PROFILE.', 'warn');
                    } else {
                        // Populate existing profile toggles
                        document.getElementById('is_diabetic').checked = !!currentUser.is_diabetic;
                        document.getElementById('has_high_bp').checked = !!currentUser.has_high_bp;
                        document.getElementById('heart_condition').checked = !!currentUser.heart_condition;
                        document.getElementById('weight_loss_goal').checked = !!currentUser.weight_loss_goal;
                        document.getElementById('is_vegan').checked = !!currentUser.is_vegan;
                        switchTab('tab-scan');
                        addLog(`DEV_SESSION_INITIALIZED: ${name} (${email})`, 'success');
                    }
                } else {
                    loginStatus.textContent = 'DEV_BYPASS_FAILED. SERVER_OFFLINE.';
                    loginStatus.style.color = 'var(--danger)';
                }
            } catch (error) {
                loginStatus.textContent = 'DEV_BYPASS_ERROR. SERVER_UNREACHABLE.';
                loginStatus.style.color = 'var(--danger)';
            } finally {
                btnDevBypass.disabled = false;
                btnDevBypass.querySelector('span').textContent = 'DEVELOPER BYPASS (DEV MODE)';
            }
        });
    }


    // =====================================================================
    // Auto-login: check if user is already signed in (Firebase persistence)
    // =====================================================================
    try {
        firebase.auth().onAuthStateChanged(async (user) => {
            if (user && !currentUser) {
                const email = user.email;
                const name = user.displayName || email.split('@')[0];
                const photoURL = user.photoURL;

                try {
                    const response = await fetch('/auth/login', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ email, name })
                    });
                    const data = await response.json();

                    if (data.status === 'success') {
                        currentUser = { email, name, photoURL, ...data.user };

                        userDisplayName.textContent = name.toUpperCase();
                        if (photoURL) {
                            profileAvatar.src = photoURL;
                            profileAvatar.style.display = 'inline-block';
                        }
                        profileEmail.textContent = email;

                        // Populate profile toggles
                        document.getElementById('is_diabetic').checked = !!currentUser.is_diabetic;
                        document.getElementById('has_high_bp').checked = !!currentUser.has_high_bp;
                        document.getElementById('heart_condition').checked = !!currentUser.heart_condition;
                        document.getElementById('weight_loss_goal').checked = !!currentUser.weight_loss_goal;
                        document.getElementById('is_vegan').checked = !!currentUser.is_vegan;

                        loginOverlay.classList.remove('active');
                        mainApp.style.display = 'block';
                        addLog(`AUTO_RESTORED_SESSION: ${name}`, 'success');
                    }
                } catch (e) {
                    // Server not reachable — stay on login screen
                    console.warn('Auto-login server sync failed:', e);
                }
            }
        });
    } catch (e) {
        console.warn('Firebase onAuthStateChanged unavailable:', e.message);
    }

    // =====================================================================
    // Logout
    // =====================================================================
    btnLogout.addEventListener('click', async () => {
        try {
            await firebase.auth().signOut();
        } catch (e) {
            // Ignore sign-out errors
        }
        currentUser = null;
        mainApp.style.display = 'none';
        loginOverlay.classList.add('active');
        loginStatus.textContent = '';

        // Reset UI
        currentFile = null;
        imagePreview.classList.add('hidden');
        uploadContent.classList.remove('hidden');
        resultsDiv.classList.add('hidden');
        analyzeBtn.classList.add('hidden');
        btnTabDiagnostics.disabled = true;
        terminal.innerHTML = '<div class="terminal-line cmd">Ready to analyze food labels.</div>';
    });

    // =====================================================================
    // Profile Save Flow
    // =====================================================================
    btnSaveProfile.addEventListener('click', async () => {
        if (!currentUser) return;
        
        btnSaveProfile.textContent = 'SAVING...';
        btnSaveProfile.disabled = true;

        const profileData = {
            email: currentUser.email,
            is_diabetic: document.getElementById('is_diabetic').checked,
            has_high_bp: document.getElementById('has_high_bp').checked,
            heart_condition: document.getElementById('heart_condition').checked,
            weight_loss_goal: document.getElementById('weight_loss_goal').checked,
            is_vegan: document.getElementById('is_vegan').checked
        };

        try {
            const response = await fetch('/auth/profile', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(profileData)
            });
            const data = await response.json();

            if (data.status === 'success') {
                // Update local user state
                currentUser.is_diabetic = profileData.is_diabetic;
                currentUser.has_high_bp = profileData.has_high_bp;
                currentUser.heart_condition = profileData.heart_condition;
                currentUser.weight_loss_goal = profileData.weight_loss_goal;
                currentUser.is_vegan = profileData.is_vegan;

                btnSaveProfile.textContent = 'PROFILE_SYNCED';
                saveStatus.textContent = 'All conditions saved to database.';
                saveStatus.style.opacity = '1';
                setTimeout(() => { saveStatus.style.opacity = '0'; }, 3000);
            } else {
                btnSaveProfile.textContent = 'SYNC_FAILED';
            }
        } catch (e) {
            btnSaveProfile.textContent = 'CONNECTION_ERROR';
        }

        setTimeout(() => {
            btnSaveProfile.textContent = 'SAVE_HEALTH_PROFILE';
            btnSaveProfile.disabled = false;
        }, 2000);
    });

    // =====================================================================
    // Tab Switching
    // =====================================================================
    function switchTab(targetId) {
        tabBtns.forEach(btn => {
            if(btn.dataset.target === targetId) btn.classList.add('active');
            else btn.classList.remove('active');
        });
        tabPanes.forEach(pane => {
            if(pane.id === targetId) pane.classList.add('active');
            else pane.classList.remove('active');
        });
    }

    tabBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            if(btn.disabled) return;
            switchTab(btn.dataset.target);
        });
    });

    // =====================================================================
    // Terminal Utilities
    // =====================================================================
    function typeWriter(element, text, index = 0, speed = 15) {
        if (index < text.length) {
            element.textContent += text.charAt(index);
            terminal.scrollTop = terminal.scrollHeight;
            setTimeout(() => typeWriter(element, text, index + 1, speed), speed);
        }
    }

    function addLog(msg, type = '') {
        const line = document.createElement('div');
        line.className = `terminal-line ${type}`;
        line.textContent = ``;
        terminal.appendChild(line);
        typeWriter(line, msg);
    }

    // =====================================================================
    // File Handling
    // =====================================================================
    dropZone.addEventListener('click', () => fileInput.click());
    dropZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropZone.style.borderColor = 'var(--primary)';
        dropZone.style.background = 'var(--primary-light)';
    });
    dropZone.addEventListener('dragleave', () => {
        dropZone.style.borderColor = 'var(--accent)';
        dropZone.style.background = 'var(--primary-light)';
    });
    dropZone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropZone.style.borderColor = 'var(--accent)';
        dropZone.style.background = 'var(--primary-light)';
        if (e.dataTransfer.files.length) handleFile(e.dataTransfer.files[0]);
    });
    fileInput.addEventListener('change', (e) => {
        if (e.target.files.length) handleFile(e.target.files[0]);
    });

    function handleFile(file) {
        if (!file.type.startsWith('image/')) {
            addLog('Please select a valid image file (JPG, PNG or WEBP).', 'warn');
            return;
        }
        currentFile = file;
        const reader = new FileReader();
        reader.onload = (e) => {
            imagePreview.src = e.target.result;
            imagePreview.classList.remove('hidden');
            uploadContent.classList.add('hidden');
            analyzeBtn.classList.remove('hidden');
            addLog(`Uploaded: ${file.name} (${(file.size/1024).toFixed(1)} KB)`, 'success');
        };
        reader.readAsDataURL(file);
    }

    // =====================================================================
    // Analysis Pipeline
    // =====================================================================
    analyzeBtn.addEventListener('click', async () => {
        if (!currentFile || !currentUser) return;
        
        analyzeBtn.classList.add('hidden');
        scanEffect.classList.remove('hidden');
        radarEffect.classList.remove('hidden');
        addLog('Analyzing label image...', 'cmd');
        
        const formData = new FormData();
        formData.append('file', currentFile);
        formData.append('email', currentUser.email);
        
        // Show which profile conditions are active
        const activeConditions = [];
        if (currentUser.is_diabetic) activeConditions.push('Diabetic');
        if (currentUser.has_high_bp) activeConditions.push('Hypertension');
        if (currentUser.heart_condition) activeConditions.push('Heart-Healthy');
        if (currentUser.weight_loss_goal) activeConditions.push('Weight Management');
        if (currentUser.is_vegan) activeConditions.push('Vegan');

        setTimeout(() => addLog('Retrieving your health profile...', 'cmd'), 500);
        if (activeConditions.length > 0) {
            setTimeout(() => addLog(`Applying rules for: ${activeConditions.join(', ')}`, 'warn'), 1000);
        } else {
            setTimeout(() => addLog('Applying default nutritional guidelines.', 'cmd'), 1000);
        }
        setTimeout(() => addLog('Reading text from food label...', 'cmd'), 1500);
        
        try {
            const response = await fetch('/analyze', {
                method: 'POST',
                body: formData
            });
            const data = await response.json();
            
            if (data.status === 'success') {
                addLog('Nutrition facts extracted successfully!', 'success');
                setTimeout(() => {
                    scanEffect.classList.add('hidden');
                    radarEffect.classList.add('hidden');
                    btnTabDiagnostics.disabled = false;
                    switchTab('tab-diagnostics');
                    displayResults(data, activeConditions);
                }, 1500);
            } else {
                addLog('Analysis failed: ' + (data.message || 'Unknown error'), 'warn');
                scanEffect.classList.add('hidden');
                radarEffect.classList.add('hidden');
                analyzeBtn.classList.remove('hidden');
            }
        } catch (error) {
            addLog('Connection lost. Please make sure the backend server is running.', 'warn');
            scanEffect.classList.add('hidden');
            radarEffect.classList.add('hidden');
            analyzeBtn.classList.remove('hidden');
        }
    });

    // =====================================================================
    // Display Results (with personalization info)
    // =====================================================================
    function displayResults(data, activeConditions) {
        resultsDiv.classList.remove('hidden');
        loadingDiv.classList.add('hidden');
        
        const finalResult = data.final_result;
        const score = (finalResult.final_health_score * 100).toFixed(0);
        
        const scoreValue = document.getElementById('score-value');
        scoreValue.textContent = score;
        
        const scoreCircle = document.getElementById('score-circle');
        let color = '#2e7d32'; // Healthy Green
        let textVerdict = 'Healthy';
        if (finalResult.risk_level === 'Moderate') {
            color = '#f57c00'; // Orange
            textVerdict = 'Moderate';
        } else if (finalResult.risk_level === 'High') {
            color = '#c62828'; // Red
            textVerdict = 'Unhealthy';
        }
        
        scoreCircle.style.background = `conic-gradient(${color} ${score}%, #e0e0e0 0%)`;
        scoreValue.style.color = color;

        const riskBadge = document.getElementById('risk-badge');
        riskBadge.textContent = textVerdict;
        riskBadge.style.backgroundColor = color + '15';
        riskBadge.style.color = color;
        riskBadge.style.border = `2px solid ${color}`;
        riskBadge.style.padding = '6px 16px';
        riskBadge.style.borderRadius = '20px';
        riskBadge.style.fontSize = '0.9rem';
        riskBadge.style.fontWeight = 'bold';
        riskBadge.style.boxShadow = 'none';

        const summary = document.getElementById('ai-verdict-summary');
        if (activeConditions.length > 0) {
            summary.textContent = `Based on your diet settings (${activeConditions.join(', ')}), this product is rated ${textVerdict.toLowerCase()} for your consumption with a health score of ${score}/100.`;
        } else {
            summary.textContent = `Standard nutritional evaluation: This product is rated ${textVerdict.toLowerCase()} with a health score of ${score}/100.`;
        }

        // Show personalization badges if any conditions are active
        const badgesDiv = document.getElementById('personalization-badges');
        const conditionsDiv = document.getElementById('active-conditions');
        conditionsDiv.innerHTML = '';

        if (activeConditions.length > 0) {
            badgesDiv.classList.remove('hidden');
            const conditionLabels = {
                'Diabetic': { icon: '🩸', desc: 'Strict Sugar & Carb Limit' },
                'Hypertension': { icon: '💉', desc: 'Strict Sodium Limit' },
                'Heart-Healthy': { icon: '❤️', desc: 'Low Saturated Fat & Cholesterol' },
                'Weight Management': { icon: '⚖️', desc: 'Favors low calorie density' },
                'Vegan': { icon: '🌿', desc: 'Animal product checks' }
            };
            activeConditions.forEach(cond => {
                const info = conditionLabels[cond] || { icon: '⚙️', desc: cond };
                const badge = document.createElement('div');
                badge.className = 'condition-badge';
                badge.innerHTML = `<span>${info.icon}</span> <span>${cond}</span> <small>${info.desc}</small>`;
                conditionsDiv.appendChild(badge);
            });
        } else {
            badgesDiv.classList.add('hidden');
        }

        // Nutrient table with fully human friendly mappings
        const nutrientList = document.getElementById('nutrient-list');
        nutrientList.innerHTML = '';

        const nutrientFriendlyNames = {
            'energy_kcal': 'Energy / Calories',
            'protein_g': 'Protein',
            'fat_g': 'Total Fat',
            'saturated_fat_g': 'Saturated Fat',
            'trans_fat_g': 'Trans Fat',
            'cholesterol_mg': 'Cholesterol',
            'sodium_mg': 'Sodium',
            'carbohydrates_g': 'Total Carbohydrates',
            'sugar_g': 'Total Sugars',
            'fiber_g': 'Dietary Fiber'
        };

        for (const [key, val] of Object.entries(data.raw_nutrition)) {
            const tr = document.createElement('tr');
            const formattedKey = nutrientFriendlyNames[key] || key.toUpperCase().replace(/_/g, ' ');
            const formattedVal = val.value + (val.unit ? ' ' + val.unit : '');
            
            let limitDisplay = 'No Limit';
            if (val.who_limit) {
                const unit = (key === 'sodium' || key === 'cholesterol') ? ' mg' : ' g';
                limitDisplay = val.who_limit + unit;
            }
            
            let valColor = 'var(--text-main)';
            if (val.percent_daily > 20) valColor = 'var(--danger)';
            else if (val.percent_daily > 10) valColor = 'var(--warning)';

            tr.innerHTML = `
                <td class="nutrient-name">${formattedKey}</td>
                <td class="nutrient-val" style="color: ${valColor}">${formattedVal}</td>
                <td class="nutrient-val" style="color: var(--text-muted); font-size: 0.95rem; font-weight: 500;">${limitDisplay}</td>
            `;
            nutrientList.appendChild(tr);
        }

        // Insights / flags
        const insightContainer = document.getElementById('insight-container');
        insightContainer.innerHTML = '';
        
        if (finalResult.flags && finalResult.flags.length > 0) {
            finalResult.flags.forEach(flag => {
                const div = document.createElement('div');
                div.className = `insight-item ${flag.type === 'risk' ? 'risk' : ''}`;
                const icon = flag.type === 'risk' ? '⚠️' : 'ℹ️';
                const typeText = flag.type === 'risk' ? 'Health Warning' : 'Nutritional Info';
                div.innerHTML = `
                    <div class="insight-title">
                        <span>${icon}</span>
                        <span>${typeText}</span>
                    </div>
                    <div style="font-size: 1rem; color: var(--text-main); line-height: 1.5; font-weight: 500;">${flag.message}</div>
                `;
                insightContainer.appendChild(div);
            });
        } else {
            insightContainer.innerHTML = '<div class="insight-item"><div class="insight-title"><span>✅</span> Product Checked</div><div style="font-size: 1rem; color: var(--text-main); font-weight: 500;">No risk factors or allergen matches detected. Suitable for your dietary profile.</div></div>';
        }
    }

    // =====================================================================
    // Reset
    // =====================================================================
    resetBtn.addEventListener('click', () => {
        currentFile = null;
        imagePreview.classList.add('hidden');
        uploadContent.classList.remove('hidden');
        resultsDiv.classList.add('hidden');
        loadingDiv.classList.remove('hidden');
        analyzeBtn.classList.add('hidden');
        btnTabDiagnostics.disabled = true;
        switchTab('tab-scan');
        addLog('Ready for next label.', 'cmd');
    });

    // =====================================================================
    // Background Animation
    // =====================================================================
    setInterval(() => {
        const bg1 = document.querySelector('.bg-1');
        const bg2 = document.querySelector('.bg-2');
        if (bg1.classList.contains('active')) {
            bg1.classList.remove('active');
            bg2.classList.add('active');
        } else {
            bg2.classList.remove('active');
            bg1.classList.add('active');
        }
    }, 15000);
});
