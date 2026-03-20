package com.chg.progeresseye.data.di

import com.chg.progeresseye.data.repository.AlertRepositoryImpl
import com.chg.progeresseye.data.repository.PolicyRepositoryImpl
import com.chg.progeresseye.data.repository.UserPlanRepositoryImpl
import com.chg.progeresseye.domain.repository.AlertRepository
import com.chg.progeresseye.domain.repository.PolicyRepository
import com.chg.progeresseye.domain.repository.UserPlanRepository
import dagger.Binds
import dagger.Module
import dagger.hilt.InstallIn
import dagger.hilt.components.SingletonComponent
import javax.inject.Singleton

@Module
@InstallIn(SingletonComponent::class)
abstract class DataModule {

    @Binds
    @Singleton
    abstract fun bindAlertRepository(impl: AlertRepositoryImpl): AlertRepository

    @Binds
    @Singleton
    abstract fun bindUserPlanRepository(impl: UserPlanRepositoryImpl): UserPlanRepository

    @Binds
    @Singleton
    abstract fun bindPolicyRepository(impl: PolicyRepositoryImpl): PolicyRepository

    @Binds
    @Singleton
    abstract fun bindDeviceRepository(impl: com.chg.progeresseye.data.repository.DeviceRepositoryImpl): com.chg.progeresseye.domain.repository.DeviceRepository

    @Binds
    @Singleton
    abstract fun bindAuthRepository(impl: com.chg.progeresseye.data.repository.AuthRepositoryImpl): com.chg.progeresseye.domain.repository.AuthRepository
}
