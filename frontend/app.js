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
    let lastAnalyzedNutrients = null;
    let lastAnalyzedProductName = "";

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

    // Helper: sync a Firebase user with our backend after login
    async function syncFirebaseUserWithBackend(user) {
        const email = user.email;
        const name = user.displayName || email.split('@')[0];
        const photoURL = user.photoURL;

        loginStatus.textContent = 'FIREBASE_AUTH_SUCCESS. SYNCING_WITH_SERVER...';
        loginStatus.style.color = 'var(--success)';

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
            loginOverlay.classList.remove('active');
            mainApp.style.display = 'block';

            if (data.is_new_user) {
                switchTab('tab-profile');
                addLog('NEW_USER_DETECTED. CONFIGURE_HEALTH_PROFILE.', 'warn');
            } else {
                if (currentUser.age) document.getElementById('user_age').value = currentUser.age;
                document.getElementById('is_diabetic').checked = !!currentUser.is_diabetic;
                document.getElementById('has_high_bp').checked = !!currentUser.has_high_bp;
                document.getElementById('heart_condition').checked = !!currentUser.heart_condition;
                document.getElementById('weight_loss_goal').checked = !!currentUser.weight_loss_goal;
                document.getElementById('is_vegan').checked = !!currentUser.is_vegan;
                switchTab('tab-scan');
                addLog(`SESSION_INITIALIZED: ${name} (${email})`, 'success');
            }
            fetchDailyIntake();
        } else {
            loginStatus.textContent = 'SERVER_SYNC_FAILED. TRY_AGAIN.';
            loginStatus.style.color = 'var(--danger)';
        }
    }

    // Handle redirect result on page load (for signInWithRedirect flow)
    try {
        firebase.auth().getRedirectResult().then(async (result) => {
            if (result && result.user) {
                loginStatus.textContent = 'GOOGLE_REDIRECT_SUCCESS. SYNCING...';
                loginStatus.style.color = 'var(--success)';
                await syncFirebaseUserWithBackend(result.user);
            }
        }).catch((error) => {
            if (error.code && error.code !== 'auth/no-current-user') {
                console.warn('Redirect result error:', error);
                loginStatus.textContent = `REDIRECT_AUTH_ERROR: ${error.code}`;
                loginStatus.style.color = 'var(--danger)';
            }
        });
    } catch (e) {
        console.warn('getRedirectResult not available:', e);
    }

    btnGoogleLogin.addEventListener('click', async () => {
        btnGoogleLogin.disabled = true;
        btnGoogleLogin.querySelector('span').textContent = 'AUTHENTICATING...';
        loginStatus.textContent = '';

        if (!googleProvider) {
            loginStatus.textContent = 'FIREBASE_AUTH_UNAVAILABLE. USE DEV BYPASS.';
            loginStatus.style.color = 'var(--danger)';
            btnGoogleLogin.disabled = false;
            btnGoogleLogin.querySelector('span').textContent = 'Sign in with Google';
            return;
        }

        try {
            // Try popup first
            const result = await firebase.auth().signInWithPopup(googleProvider);
            await syncFirebaseUserWithBackend(result.user);
        } catch (error) {
            console.error('Popup login error:', error);

            // If popup was blocked or domain is unauthorized, fall back to redirect
            if (
                error.code === 'auth/popup-blocked' ||
                error.code === 'auth/unauthorized-domain' ||
                error.code === 'auth/operation-not-supported-in-this-environment'
            ) {
                loginStatus.textContent = 'POPUP_BLOCKED. REDIRECTING_TO_GOOGLE...';
                loginStatus.style.color = 'var(--warning)';
                try {
                    await firebase.auth().signInWithRedirect(googleProvider);
                    // Page will redirect — no further code runs here
                    return;
                } catch (redirectErr) {
                    loginStatus.textContent = `REDIRECT_ERROR: ${redirectErr.code || redirectErr.message}`;
                    loginStatus.style.color = 'var(--danger)';
                }
            } else if (error.code === 'auth/popup-closed-by-user') {
                loginStatus.textContent = 'Login cancelled. Please try again.';
            } else if (error.code === 'auth/network-request-failed') {
                loginStatus.textContent = 'Network error. Check your internet connection.';
            } else if (error.code === 'auth/configuration-not-found') {
                loginStatus.textContent = 'Firebase not configured. Check firebase_config.js.';
            } else {
                loginStatus.textContent = `AUTH_ERROR: ${error.code || error.message || 'UNKNOWN'}`;
            }
            loginStatus.style.color = 'var(--danger)';
        } finally {
            btnGoogleLogin.disabled = false;
            btnGoogleLogin.querySelector('span').textContent = 'Sign in with Google';
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
                        if (currentUser.age) document.getElementById('user_age').value = currentUser.age;
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
                        if (currentUser.age) document.getElementById('user_age').value = currentUser.age;
                        document.getElementById('is_diabetic').checked = !!currentUser.is_diabetic;
                        document.getElementById('has_high_bp').checked = !!currentUser.has_high_bp;
                        document.getElementById('heart_condition').checked = !!currentUser.heart_condition;
                        document.getElementById('weight_loss_goal').checked = !!currentUser.weight_loss_goal;
                        document.getElementById('is_vegan').checked = !!currentUser.is_vegan;

                        loginOverlay.classList.remove('active');
                        mainApp.style.display = 'block';
                        addLog(`AUTO_RESTORED_SESSION: ${name}`, 'success');
                        fetchDailyIntake();
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
            age: parseInt(document.getElementById('user_age').value) || null,
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
                currentUser.age = profileData.age;
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
                lastAnalyzedNutrients = data.nutrition_data;
                lastAnalyzedProductName = currentFile ? currentFile.name.replace(/\.[^/.]+$/, "") : "Scanned Product";
                
                // Reset log consumption button text
                const btnLogConsumption = document.getElementById('log-consumption-btn');
                if (btnLogConsumption) {
                    btnLogConsumption.textContent = 'Log Consumption';
                    btnLogConsumption.disabled = false;
                }

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
    // Log Consumption & Log Book logic
    // =====================================================================
    const btnLogConsumption = document.getElementById('log-consumption-btn');
    
    if (btnLogConsumption) {
        btnLogConsumption.addEventListener('click', async () => {
            if (!currentUser || !lastAnalyzedNutrients) return;
            
            btnLogConsumption.textContent = 'LOGGING...';
            btnLogConsumption.disabled = true;
            
            const payload = {
                email: currentUser.email,
                product_name: lastAnalyzedProductName,
                energy_kcal: lastAnalyzedNutrients.energy_kcal || 0.0,
                sugars_g: lastAnalyzedNutrients.sugars_g || 0.0,
                sodium_mg: lastAnalyzedNutrients.sodium_mg || 0.0,
                saturated_fat_g: lastAnalyzedNutrients.saturated_fat_g || 0.0,
                protein_g: lastAnalyzedNutrients.protein_g || 0.0,
                carbohydrates_g: lastAnalyzedNutrients.carbohydrates_g || 0.0,
                fat_g: lastAnalyzedNutrients.fat_g || 0.0
            };
            
            try {
                const response = await fetch('/intake/log', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
                const data = await response.json();
                if (data.status === 'success') {
                    btnLogConsumption.textContent = 'LOGGED!';
                    addLog(`Logged consumption of ${lastAnalyzedProductName}.`, 'success');
                    
                    // Refresh Log Book values
                    await fetchDailyIntake();
                    
                    // Switch to Log Book tab after a short delay
                    setTimeout(() => {
                        switchTab('tab-intake');
                    }, 800);
                } else {
                    btnLogConsumption.textContent = 'FAILED TO LOG';
                }
            } catch (e) {
                btnLogConsumption.textContent = 'CONNECTION ERROR';
                console.error(e);
            }
            
            setTimeout(() => {
                btnLogConsumption.textContent = 'Log Consumption';
                btnLogConsumption.disabled = false;
            }, 2500);
        });
    }

    async function fetchDailyIntake() {
        if (!currentUser) return;
        
        try {
            const response = await fetch(`/intake/daily?email=${encodeURIComponent(currentUser.email)}`);
            const data = await response.json();
            
            if (data.status === 'success') {
                // Update Progress bars & values
                const nutrients = [
                    { id: 'calories', key: 'energy_kcal', unit: 'kcal' },
                    { id: 'sugar', key: 'sugars_g', unit: 'g' },
                    { id: 'sodium', key: 'sodium_mg', unit: 'mg' },
                    { id: 'satfat', key: 'saturated_fat_g', unit: 'g' }
                ];
                
                nutrients.forEach(n => {
                    const consumed = data.totals[n.key] || 0.0;
                    const limit = data.limits[n.key];
                    const pct = data.percentages[n.key] || 0.0;
                    
                    const valEl = document.getElementById(`intake-val-${n.id}`);
                    const barEl = document.getElementById(`intake-bar-${n.id}`);
                    
                    if (valEl && barEl) {
                        valEl.textContent = `${consumed.toFixed(1)} / ${limit.toFixed(0)} ${n.unit} (${pct.toFixed(0)}%)`;
                        barEl.style.width = `${pct}%`;
                        
                        // Set colors depending on warning threshold
                        barEl.className = 'progress-bar'; // reset
                        if (pct >= 100) {
                            barEl.classList.add('danger');
                        } else if (pct >= 80) {
                            barEl.classList.add('warning');
                        }
                    }
                });
                
                // Render dietitian recommendations
                const suggestionsEl = document.getElementById('intake-suggestions');
                if (suggestionsEl) {
                    suggestionsEl.innerHTML = '';
                    if (data.suggestions && data.suggestions.length > 0) {
                        const ul = document.createElement('ul');
                        data.suggestions.forEach(sug => {
                            const li = document.createElement('li');
                            li.textContent = sug;
                            ul.appendChild(li);
                        });
                        suggestionsEl.appendChild(ul);
                    }
                }
                
                // Render consumed foods list
                const listEl = document.getElementById('intake-list');
                const emptyEl = document.getElementById('intake-list-empty');
                
                if (listEl && emptyEl) {
                    listEl.innerHTML = '';
                    if (data.items && data.items.length > 0) {
                        emptyEl.classList.add('hidden');
                        data.items.forEach(item => {
                            const li = document.createElement('li');
                            li.className = 'intake-item-row';
                            
                            let timeDisplay = "";
                            if (item.timestamp) {
                                try {
                                    const dateObj = new Date(item.timestamp);
                                    timeDisplay = dateObj.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
                                } catch(err) {
                                    timeDisplay = item.timestamp;
                                }
                            }
                            
                            li.innerHTML = `
                                <div class="intake-item-info">
                                    <span class="intake-item-name">${item.product_name}</span>
                                    <span class="intake-item-meta">${timeDisplay} • ${item.energy_kcal.toFixed(0)} kcal • Sugar: ${item.sugars_g.toFixed(1)}g • Sodium: ${item.sodium_mg.toFixed(0)}mg</span>
                                </div>
                                <button class="intake-delete-btn" data-id="${item.id}" title="Remove entry">🗑️</button>
                            `;
                            
                            const deleteBtn = li.querySelector('.intake-delete-btn');
                            deleteBtn.addEventListener('click', async () => {
                                const itemId = deleteBtn.dataset.id;
                                if (confirm(`Are you sure you want to remove "${item.product_name}" from your intake log?`)) {
                                    try {
                                        const delResponse = await fetch(`/intake/delete/${itemId}?email=${encodeURIComponent(currentUser.email)}`, {
                                            method: 'DELETE'
                                        });
                                        const delData = await delResponse.json();
                                        if (delData.status === 'success') {
                                            addLog(`Removed "${item.product_name}" from Log Book.`, 'success');
                                            fetchDailyIntake();
                                        }
                                    } catch(err) {
                                        console.error('Failed to delete item:', err);
                                    }
                                }
                            });
                            
                            listEl.appendChild(li);
                        });
                    } else {
                        emptyEl.classList.remove('hidden');
                    }
                }
            }
        } catch (e) {
            console.error('Failed to fetch daily intake:', e);
        }
    }

    // Call fetchDailyIntake if switching tab directly to Log Book
    tabBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            if (btn.dataset.target === 'tab-intake') {
                fetchDailyIntake();
            }
        });
    });

    // Save profile also triggers limits update
    btnSaveProfile.addEventListener('click', () => {
        setTimeout(() => {
            fetchDailyIntake();
        }, 1000);
    });

    // =====================================================================
    // Background Slideshow — 3 nutrition images cycling
    // =====================================================================
    const bgSlides = document.querySelectorAll('.bg-slide');
    let currentSlide = 0;

    if (bgSlides.length > 0) {
        setInterval(() => {
            bgSlides[currentSlide].classList.remove('active');
            currentSlide = (currentSlide + 1) % bgSlides.length;
            bgSlides[currentSlide].classList.add('active');
        }, 8000);
    }

    // =====================================================================
    // Dark Mode Toggle
    // =====================================================================
    const themeToggle = document.getElementById('theme-toggle');
    if (themeToggle) {
        // Load saved theme
        const savedTheme = localStorage.getItem('nutriscan-theme') || 'light';
        if (savedTheme === 'dark') {
            document.body.setAttribute('data-theme', 'dark');
            themeToggle.textContent = '☀️';
        }

        themeToggle.addEventListener('click', () => {
            const isDark = document.body.getAttribute('data-theme') === 'dark';
            if (isDark) {
                document.body.removeAttribute('data-theme');
                themeToggle.textContent = '🌙';
                localStorage.setItem('nutriscan-theme', 'light');
            } else {
                document.body.setAttribute('data-theme', 'dark');
                themeToggle.textContent = '☀️';
                localStorage.setItem('nutriscan-theme', 'dark');
            }
            if (macroChartInst) updateChartTheme();
        });
    }

    // =====================================================================
    // Export PDF
    // =====================================================================
    const btnDownloadPdf = document.getElementById('download-pdf-btn');
    if (btnDownloadPdf) {
        btnDownloadPdf.addEventListener('click', () => {
                console.log('Export PDF button clicked');
            try {
                const element = document.getElementById('results');
                // Ensure the results section is visible for PDF capture
                const wasHidden = element.classList.contains('hidden');
                if (wasHidden) element.classList.remove('hidden');
                const opt = {
                    margin: 10,
                    filename: 'NutriScan_Report.pdf',
                    image: { type: 'jpeg', quality: 0.98 },
                    html2canvas: { scale: 2, useCORS: true },
                    jsPDF: { unit: 'mm', format: 'a4', orientation: 'portrait' }
                };
                btnDownloadPdf.textContent = 'Exporting...';
                html2pdf().set(opt).from(element).save().then(() => {
                    btnDownloadPdf.textContent = 'Export PDF';
                    // Restore hidden state if it was originally hidden
                    if (wasHidden) element.classList.add('hidden');
                }).catch((err) => {
                    console.error('PDF generation failed: ', err);
                    alert('PDF generation failed. Check console for details.');
                    btnDownloadPdf.textContent = 'Export PDF';
                    if (wasHidden) element.classList.add('hidden');
                });
            } catch (err) {
                console.error("Error initiating PDF generation: ", err);
                alert("Could not start PDF export. Make sure html2pdf is loaded.");
            }
        });
    }

    // =====================================================================
    // Chart.js Integration
    // =====================================================================
    let macroChartInst = null;
    const ctx = document.getElementById('macroChart');
    if (ctx) {
        macroChartInst = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: ['Protein', 'Carbs', 'Fat'],
                datasets: [{
                    data: [0, 0, 0],
                    backgroundColor: ['#2e7d32', '#f57c00', '#c62828'],
                    borderWidth: 0
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                cutout: '70%',
                plugins: {
                    legend: { position: 'bottom', labels: { color: 'var(--text-main)' } }
                }
            }
        });
    }

    function updateChartTheme() {
        if (!macroChartInst) return;
        const isDark = document.body.getAttribute('data-theme') === 'dark';
        macroChartInst.options.plugins.legend.labels.color = isDark ? '#e8f5e9' : '#1b2e1e';
        macroChartInst.update();
    }

    // Monkey-patch fetchDailyIntake to update the chart
    const originalFetchDailyIntake = fetchDailyIntake;
    fetchDailyIntake = async function() {
        await originalFetchDailyIntake();
        if (!currentUser) return;
        try {
            const response = await fetch(`/intake/daily?email=${encodeURIComponent(currentUser.email)}`);
            const data = await response.json();
            if (data.status === 'success' && macroChartInst) {
                const p = data.totals['protein_g'] || 0;
                const c = data.totals['carbohydrates_g'] || 0;
                const f = data.totals['fat_g'] || 0;
                macroChartInst.data.datasets[0].data = [p, c, f];
                macroChartInst.update();
            }
        } catch(e) {}
    };

    // =====================================================================
    // Barcode Scanning via OpenFoodFacts
    // =====================================================================
    const btnBarcode = document.getElementById('barcode-btn');
    if (btnBarcode) {
        btnBarcode.addEventListener('click', async () => {
            if (!currentUser) return;
            const barcode = prompt("Enter the product barcode (e.g., 049000028904):");
            if (!barcode || barcode.trim() === '') return;

            analyzeBtn.classList.add('hidden');
            btnBarcode.classList.add('hidden');
            scanEffect.classList.remove('hidden');
            radarEffect.classList.remove('hidden');
            addLog(`Fetching data for barcode: ${barcode}...`, 'cmd');

            const activeConditions = [];
            if (currentUser.is_diabetic) activeConditions.push('Diabetic');
            if (currentUser.has_high_bp) activeConditions.push('Hypertension');
            if (currentUser.heart_condition) activeConditions.push('Heart-Healthy');
            if (currentUser.weight_loss_goal) activeConditions.push('Weight Management');
            if (currentUser.is_vegan) activeConditions.push('Vegan');

            try {
                const response = await fetch('/analyze/barcode', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ barcode: barcode, email: currentUser.email })
                });
                const data = await response.json();

                if (data.status === 'success') {
                    addLog('Barcode mapped to nutrition facts!', 'success');
                    lastAnalyzedNutrients = data.nutrition_data;
                    lastAnalyzedProductName = data.product_name || `Barcode: ${barcode}`;

                    const btnLogConsumption = document.getElementById('log-consumption-btn');
                    if (btnLogConsumption) {
                        btnLogConsumption.textContent = 'Log Consumption';
                        btnLogConsumption.disabled = false;
                    }

                    setTimeout(() => {
                        scanEffect.classList.add('hidden');
                        radarEffect.classList.add('hidden');
                        btnTabDiagnostics.disabled = false;
                        switchTab('tab-diagnostics');
                        displayResults(data, activeConditions);
                        btnBarcode.classList.remove('hidden');
                    }, 1500);
                } else {
                    addLog('Barcode analysis failed: ' + (data.message || 'Product not found'), 'warn');
                    scanEffect.classList.add('hidden');
                    radarEffect.classList.add('hidden');
                    analyzeBtn.classList.remove('hidden');
                    btnBarcode.classList.remove('hidden');
                }
            } catch (error) {
                addLog('Connection lost. Please make sure the backend server is running.', 'warn');
                scanEffect.classList.add('hidden');
                radarEffect.classList.add('hidden');
                analyzeBtn.classList.remove('hidden');
                btnBarcode.classList.remove('hidden');
            }
        });
    }
});

